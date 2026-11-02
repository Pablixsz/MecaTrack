"""
Pruebas de integracion del CRUD /api/v1/services (Flask + PostgreSQL real).

El seed de conftest deja el servicio 1 'Cambio de aceite' y los usuarios
owner@test.com, mechanic@test.com y client@test.com.
"""

URL = '/api/v1/services'

NEW_SERVICE = {
    'service_name': 'Cambio de pastillas de freno',
    'description': 'Reemplazo de pastillas delanteras',
    'estimated_duration_minutes': 90,
    'base_price': 150000,
}


def _assert_error(response, status, code):
    assert response.status_code == status, response.get_json()
    body = response.get_json()
    assert set(body) == {'code', 'message', 'details'}
    assert body['code'] == code
    assert isinstance(body['message'], str) and body['message']
    return body


# --- Las 3 pruebas minimas que pide la guia --------------------------------

def test_post_creates_service_and_get_reads_it(login):
    owner = login('owner@test.com')

    created = owner.post(URL, json=NEW_SERVICE)
    assert created.status_code == 201, created.get_json()
    body = created.get_json()
    assert body['service_id'] == 2 and body['status'] == 'active'

    fetched = owner.get(f"{URL}/{body['service_id']}")
    assert fetched.status_code == 200
    assert fetched.get_json() == body


def test_get_unknown_id_returns_404_with_error_format(app):
    body = _assert_error(app.test_client().get(f'{URL}/9999'), 404, 'not_found')
    assert body['details'] == {'service_id': 9999}


def test_post_invalid_body_returns_422_with_field_details(login):
    owner = login('owner@test.com')
    response = owner.post(URL, json={'service_name': '  ', 'estimated_duration_minutes': 'una hora',
                                     'base_price': -5, 'color': 'rojo'})
    body = _assert_error(response, 422, 'validation_error')
    assert set(body['details']) == {'service_name', 'estimated_duration_minutes', 'base_price', 'color'}


# --- Cobertura adicional ----------------------------------------------------

def test_list_is_public_and_filters_by_status(app, login):
    owner = login('owner@test.com')
    owner.post(URL, json={**NEW_SERVICE, 'status': 'inactive'})
    anonymous = app.test_client()

    assert [s['service_id'] for s in anonymous.get(URL).get_json()] == [1]
    assert [s['service_id'] for s in anonymous.get(f'{URL}?status=all').get_json()] == [1, 2]
    _assert_error(anonymous.get(f'{URL}?status=deleted'), 422, 'validation_error')


def test_write_endpoints_require_owner_or_admin(app, login):
    anonymous = app.test_client()
    # Sin sesion: 401 antes de validar el cuerpo (aunque sea invalido)
    _assert_error(anonymous.post(URL, json={}), 401, 'unauthorized')
    _assert_error(anonymous.delete(f'{URL}/1'), 401, 'unauthorized')

    for email in ('client@test.com', 'mechanic@test.com'):
        user = login(email)
        body = _assert_error(user.post(URL, json=NEW_SERVICE), 403, 'forbidden')
        assert body['details']['required_roles'] == ['owner', 'admin']
        _assert_error(user.put(f'{URL}/1', json=NEW_SERVICE), 403, 'forbidden')


def test_duplicate_name_returns_409_case_insensitive(login):
    owner = login('owner@test.com')
    body = _assert_error(owner.post(URL, json={**NEW_SERVICE, 'service_name': 'CAMBIO DE ACEITE'}),
                         409, 'duplicate_service_name')
    assert body['details']['existing_service_id'] == 1

    # PUT tampoco puede renombrar un servicio al nombre de otro
    other = owner.post(URL, json=NEW_SERVICE).get_json()
    _assert_error(owner.put(f"{URL}/{other['service_id']}", json={**NEW_SERVICE, 'service_name': 'cambio de aceite'}),
                  409, 'duplicate_service_name')


def test_put_replaces_service_and_validates(login):
    owner = login('owner@test.com')
    replacement = {'service_name': 'Cambio de aceite sintetico', 'estimated_duration_minutes': 50,
                   'base_price': 110000, 'status': 'inactive'}

    response = owner.put(f'{URL}/1', json=replacement)
    assert response.status_code == 200, response.get_json()
    assert response.get_json() == {**replacement, 'service_id': 1, 'business_id': 1, 'description': None}

    _assert_error(owner.put(f'{URL}/9999', json=replacement), 404, 'not_found')
    # PUT exige la representacion completa
    body = _assert_error(owner.put(f'{URL}/1', json={'base_price': 1}), 422, 'validation_error')
    assert {'service_name', 'estimated_duration_minutes'} <= set(body['details'])


def test_delete_returns_204_404_and_409_when_booked(login):
    owner = login('owner@test.com')
    created = owner.post(URL, json=NEW_SERVICE).get_json()

    response = owner.delete(f"{URL}/{created['service_id']}")
    assert response.status_code == 204 and response.data == b''
    _assert_error(owner.get(f"{URL}/{created['service_id']}"), 404, 'not_found')
    _assert_error(owner.delete(f"{URL}/{created['service_id']}"), 404, 'not_found')

    # El servicio 1 queda con una cita: ya no se puede borrar
    client = login('client@test.com')
    vehicle = client.post('/vehicles', json={
        'license_plate': 'XYZ987', 'brand': 'Renault', 'model': 'Logan', 'year': 2018,
        'vehicle_type': 'car', 'fuel_type': 'gasoline', 'transmission_type': 'manual'}).get_json()
    booked = client.post('/appointments', json={
        'vehicle_id': vehicle['vehicle_id'], 'service_id': 1, 'scheduled_start': '2030-02-01T08:00:00'})
    assert booked.status_code == 201, booked.get_json()

    body = _assert_error(owner.delete(f'{URL}/1'), 409, 'service_has_appointments')
    assert body['details'] == {'service_id': 1, 'appointments': 1}


def test_unknown_api_route_uses_error_format_but_legacy_routes_do_not(app):
    anonymous = app.test_client()
    _assert_error(anonymous.get('/api/v1/nope'), 404, 'not_found')
    _assert_error(anonymous.patch(f'{URL}/1', json={}), 405, 'method_not_allowed')

    # Las rutas antiguas conservan su formato {"error": ...}
    legacy = anonymous.post('/services', json={})
    assert legacy.status_code == 401 and 'error' in legacy.get_json()


# --- Regresion SonarCloud S5131 (reflected XSS) -----------------------------

def test_user_input_is_echoed_only_as_non_sniffable_json(login):
    owner = login('owner@test.com')
    payload = {**NEW_SERVICE, 'service_name': '<script>alert(1)</script>'}

    response = owner.post(URL, json=payload)

    assert response.status_code == 201
    assert response.mimetype == 'application/json'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
