"""OWASP API Security Top 10 2023: one test group per control (see docs/lab7/owasp-controls.md)."""

import pytest
from werkzeug.security import check_password_hash

from api.rate_limit import limiter
from infrastructure.persistence.extensions import db
from tests.integration.conftest import PASSWORD

VEHICLE = {'license_plate': 'ABC123', 'brand': 'Mazda', 'model': '3', 'year': 2020, 'vehicle_type': 'car',
           'fuel_type': 'gasoline', 'transmission_type': 'automatic'}
REGISTER = {'first_name': 'Ana', 'last_name': 'Ruiz', 'document_number': '2001', 'email': 'ana@test.com',
            'password': 'secreto1'}


def _other_client(app):
    assert app.test_client().post('/auth/register', json={**REGISTER, 'password': PASSWORD}).status_code == 201


def _vehicle_and_appointment(client, plate='ABC123', start='2030-01-10T09:00:00'):
    vehicle_id = client.post('/vehicles', json={**VEHICLE, 'license_plate': plate}).get_json()['vehicle_id']
    response = client.post('/appointments', json={'vehicle_id': vehicle_id, 'service_id': 1, 'scheduled_start': start})
    assert response.status_code == 201, response.get_json()
    return vehicle_id, response.get_json()['appointment_id']


# --- API1: Broken Object Level Authorization -----------------------------------------

@pytest.fixture
def victim_and_attacker(app, login):
    victim = login('client@test.com')
    vehicle_id, appointment_id = _vehicle_and_appointment(victim)
    _other_client(app)
    return victim, login('ana@test.com'), vehicle_id, appointment_id


def test_api1_client_cannot_read_or_change_another_clients_vehicle(victim_and_attacker):
    _, attacker, vehicle_id, _ = victim_and_attacker
    assert attacker.get(f'/vehicles/{vehicle_id}').status_code == 403
    assert attacker.put(f'/vehicles/{vehicle_id}', json={'brand': 'X'}).status_code == 403
    assert attacker.delete(f'/vehicles/{vehicle_id}').status_code == 403
    assert attacker.get('/vehicles').get_json() == []


def test_api1_client_cannot_read_or_cancel_another_clients_appointment(victim_and_attacker):
    _, attacker, _, appointment_id = victim_and_attacker
    assert attacker.get(f'/appointments/{appointment_id}').status_code == 403
    assert attacker.get('/appointments').get_json() == []


def test_api1_client_cannot_read_or_pay_another_clients_payment(victim_and_attacker):
    victim, attacker, _, appointment_id = victim_and_attacker
    assert attacker.get(f'/payments/appointment/{appointment_id}').status_code == 403
    [deposit, _] = victim.get(f'/payments/appointment/{appointment_id}').get_json()
    assert attacker.post(f"/payments/{deposit['payment_id']}/pay", json={}).status_code == 403


# --- API2: Broken Authentication -----------------------------------------------------

@pytest.fixture
def rate_limited(app, monkeypatch):
    monkeypatch.setitem(app.config, 'LOGIN_RATE_LIMIT', '5 per minute')
    limiter.reset()
    yield
    limiter.reset()


def test_api2_login_is_rate_limited(app, rate_limited):
    client = app.test_client()
    body = {'email': 'client@test.com', 'password': 'mala'}
    assert [client.post('/api/auth/login', json=body).status_code for _ in range(5)] == [401] * 5
    response = client.post('/api/auth/login', json=body)
    assert (response.status_code, response.get_json()['code']) == (429, 'rate_limited')
    assert response.headers['X-RateLimit-Limit'] == '5'
    assert 0 < int(response.headers['Retry-After']) <= 60


def test_api2_short_passwords_are_rejected(app):
    response = app.test_client().post('/auth/register', json={**REGISTER, 'password': 'corta'})
    assert response.status_code == 400


# --- API3: Broken Object Property Level Authorization --------------------------------

def test_api3_register_ignores_a_requested_role(app):
    response = app.test_client().post('/auth/register', json={**REGISTER, 'role': 'admin'})
    assert response.status_code == 201
    login = app.test_client().post('/api/auth/login', json={'email': REGISTER['email'], 'password': 'secreto1'})
    assert login.get_json()['role'] == 'client'


def test_api3_password_hash_is_never_returned(app, login):
    owner = login('owner@test.com')
    client = login('client@test.com')
    responses = [client.get('/auth/me'), owner.get('/auth/me'), owner.get('/businesses/mechanics'),
                 owner.get('/businesses/clients'), owner.post('/businesses/clients', json=REGISTER)]
    for response in responses:
        assert response.status_code < 300
        assert 'password' not in response.get_data(as_text=True)


def test_api3_vehicle_owner_cannot_be_reassigned_through_the_body(app, login):
    client = login('client@test.com')
    vehicle_id = client.post('/vehicles', json=VEHICLE).get_json()['vehicle_id']
    client.put(f'/vehicles/{vehicle_id}', json={'owner_user_id': 1, 'brand': 'Kia'})
    [vehicle] = client.get('/vehicles').get_json()  # sigue siendo del cliente que lo creo
    assert (vehicle['vehicle_id'], vehicle['brand']) == (vehicle_id, 'Kia')


# --- API4: Unrestricted Resource Consumption -----------------------------------------

def test_api4_oversized_bodies_are_rejected(app):
    response = app.test_client().post('/api/auth/login', data='x' * (1024 * 1024 + 1), content_type='application/json')
    assert (response.status_code, response.get_json()['code']) == (413, 'error')


def test_api4_oversized_bodies_use_the_legacy_format_on_legacy_routes(app):
    response = app.test_client().post('/auth/register', data='x' * (1024 * 1024 + 1), content_type='application/json')
    assert (response.status_code, response.get_json()) == (413, {'error': 'La petición es demasiado grande'})


@pytest.mark.parametrize('query, count, first', [('', 3, 1), ('?limit=2', 2, 1), ('?limit=2&offset=2', 1, 3),
                                                 ('?limit=0', 1, 1), ('?limit=9999', 3, 1), ('?offset=-5', 3, 1)])
def test_api4_lists_are_paginated(login, query, count, first):
    client = login('client@test.com')
    ids = [client.post('/vehicles', json={**VEHICLE, 'license_plate': f'ABC{i}'}).get_json()['vehicle_id']
           for i in range(1, 4)]
    response = client.get(f'/vehicles{query}')
    body = response.get_json()
    assert len(body) == count and body[0]['vehicle_id'] == ids[first - 1]
    assert response.headers['X-Total-Count'] == '3'


def test_api4_page_size_is_capped(login, monkeypatch):
    monkeypatch.setattr('api.legacy.MAX_PAGE_SIZE', 2)
    client = login('client@test.com')
    for i in range(3):
        client.post('/vehicles', json={**VEHICLE, 'license_plate': f'ABC{i}'})
    assert len(client.get('/vehicles?limit=9999').get_json()) == 2


# --- API6: Unrestricted Access to Sensitive Business Flows ---------------------------

def test_api6_client_cannot_exceed_the_active_appointment_limit(login):
    client = login('client@test.com')
    vehicle_id = client.post('/vehicles', json=VEHICLE).get_json()['vehicle_id']
    for day in range(10, 15):
        response = client.post('/appointments', json={'vehicle_id': vehicle_id, 'service_id': 1,
                                                      'scheduled_start': f'2030-01-{day}T09:00:00'})
        assert response.status_code == 201, response.get_json()
    response = client.post('/appointments', json={'vehicle_id': vehicle_id, 'service_id': 1,
                                                  'scheduled_start': '2030-01-20T09:00:00'})
    assert response.status_code == 409
    assert response.get_json() == {'error': 'El cliente ya tiene 5 citas activas'}


def test_api6_staff_cannot_confirm_without_the_deposit(login):
    client = login('client@test.com')
    _, appointment_id = _vehicle_and_appointment(client)
    owner = login('owner@test.com')

    response = owner.put(f'/appointments/{appointment_id}/status', json={'status': 'confirmed'})

    assert response.status_code == 409
    assert client.get(f'/appointments/{appointment_id}').get_json()['status'] == 'pending'


# --- API8: Security Misconfiguration -------------------------------------------------

def test_api8_security_headers_are_present(app):
    headers = app.test_client().get('/api/v1/services').headers
    assert headers['X-Content-Type-Options'] == 'nosniff'
    assert headers['X-Frame-Options'] == 'DENY'
    assert headers['Referrer-Policy'] == 'no-referrer'
    assert headers['Content-Security-Policy'] == "default-src 'none'; frame-ancestors 'none'"
    assert 'Strict-Transport-Security' not in headers


def test_api8_hsts_is_sent_over_https(app):
    response = app.test_client().get('/api/v1/services', base_url='https://localhost')
    assert 'max-age' in response.headers['Strict-Transport-Security']


def test_api8_swagger_ui_can_load_its_cdn_assets(app):
    assert 'Content-Security-Policy' not in app.test_client().get('/docs').headers


def test_api8_cors_rejects_unknown_origins_and_never_allows_credentials(app):
    client = app.test_client()
    allowed = client.get('/api/v1/services', headers={'Origin': 'http://127.0.0.1:5500'})
    assert allowed.headers['Access-Control-Allow-Origin'] == 'http://127.0.0.1:5500'
    assert 'Access-Control-Allow-Credentials' not in allowed.headers
    evil = client.get('/api/v1/services', headers={'Origin': 'https://evil.example'})
    assert 'Access-Control-Allow-Origin' not in evil.headers


@pytest.fixture
def production_errors(app, monkeypatch):
    monkeypatch.setitem(app.config, 'PROPAGATE_EXCEPTIONS', False)
    monkeypatch.setattr(app, 'testing', False)


@pytest.mark.parametrize('url, expected', [
    ('/api/v1/services', {'code': 'internal_error', 'message': 'An unexpected error occurred', 'details': None}),
    ('/services', {'error': 'Ocurrió un error inesperado'}),
])
def test_api8_unexpected_errors_do_not_leak_internals(app, production_errors, monkeypatch, url, expected):
    def boom():
        raise RuntimeError('secret connection string')

    monkeypatch.setattr('api.legacy.service_routes.container', boom)
    monkeypatch.setattr('api.v1.services.container', boom)
    response = app.test_client().get(url)
    assert (response.status_code, response.get_json()) == (500, expected)


# --- API9: Improper Inventory Management ---------------------------------------------

def test_api9_every_api_route_is_documented(app):
    spec = app.test_client().get('/openapi.json').get_json()
    documented = set(spec['paths'])
    for rule in app.url_map.iter_rules():
        if rule.rule.startswith('/api/'):
            path = rule.rule.replace('<int:', '{').replace('<', '{').replace('>', '}')
            assert path in documented, f'{path} is missing from the OpenAPI document'


def test_passwords_are_stored_hashed(app):
    from infrastructure.persistence.models import User
    assert app.test_client().post('/auth/register', json=REGISTER).status_code == 201
    with app.app_context():
        stored = db.session.query(User).filter_by(email=REGISTER['email']).one().password_hash
        db.session.remove()
    assert stored != REGISTER['password'] and check_password_hash(stored, REGISTER['password'])
