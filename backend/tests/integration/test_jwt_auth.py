"""JWT + RBAC: login, roles, expiry, tampering, revocation and stale accounts."""

from datetime import timedelta

import jwt as pyjwt
import pytest
from flask_jwt_extended import create_access_token

from app import create_app
from config import TestConfig
from infrastructure.persistence.extensions import db
from tests.integration.conftest import PASSWORD

LOGIN = '/api/auth/login'
ADMIN_URL = '/api/rbac/admin'
USER_URL = '/api/rbac/user'


def bearer(token):
    return {'Authorization': f'Bearer {token}'}


def _token(app, email='client@test.com'):
    response = app.test_client().post(LOGIN, json={'email': email, 'password': PASSWORD})
    assert response.status_code == 200, response.get_json()
    return response.get_json()['access_token']


@pytest.fixture
def admin_user(app):
    from infrastructure.persistence.models import User
    from werkzeug.security import generate_password_hash
    with app.app_context():
        db.session.add(User(first_name='Ana', last_name='Admin', document_number='1009', email='admin@test.com',
                            role='admin', password_hash=generate_password_hash(PASSWORD)))
        db.session.commit()
        db.session.remove()
    return 'admin@test.com'


# --- Login ---------------------------------------------------------------------

def test_valid_login_returns_a_short_lived_token_with_the_role_claim(app):
    response = app.test_client().post(LOGIN, json={'email': 'client@test.com', 'password': PASSWORD})

    body = response.get_json()
    assert response.status_code == 200
    assert (body['token_type'], body['expires_in'], body['role']) == ('Bearer', 900, 'client')
    claims = pyjwt.decode(body['access_token'], options={'verify_signature': False})
    assert claims['role'] == 'client' and claims['sub'] == str(body['user_id'])
    assert claims['exp'] - claims['iat'] == 900


def test_login_sets_no_cookie_so_there_is_nothing_for_csrf_to_abuse(app):
    response = app.test_client().post(LOGIN, json={'email': 'client@test.com', 'password': PASSWORD})
    assert 'Set-Cookie' not in response.headers


@pytest.mark.parametrize('body', [{'email': 'client@test.com', 'password': 'mala'},
                                  {'email': 'nadie@test.com', 'password': PASSWORD}], ids=['password', 'email'])
def test_invalid_login_is_401_with_the_same_generic_message(app, body):
    response = app.test_client().post(LOGIN, json=body)
    assert response.status_code == 401
    assert response.get_json()['message'] == 'Credenciales inválidas'


@pytest.mark.parametrize('body', [{}, {'email': 'client@test.com'}, {'password': PASSWORD}])
def test_login_requires_email_and_password(app, body):
    assert app.test_client().post(LOGIN, json=body).status_code == 400


# --- 401 --------------------------------------------------------------------------

@pytest.mark.parametrize('url', [ADMIN_URL, USER_URL, '/appointments', '/bays'])
def test_without_token_is_401(app, url):
    assert app.test_client().get(url).status_code == 401


def test_expired_token_is_401(app):
    with app.app_context():
        token = create_access_token(identity='3', additional_claims={'role': 'client'},
                                    expires_delta=timedelta(seconds=-1))
    response = app.test_client().get(USER_URL, headers=bearer(token))
    assert (response.status_code, response.get_json()['code']) == (401, 'token_expired')


def test_token_signed_with_another_key_is_401(app):
    token = pyjwt.encode({'sub': '3', 'role': 'admin', 'type': 'access', 'jti': 'x', 'fresh': False},
                         'another-signing-key-with-enough-length-1234', algorithm='HS256')
    response = app.test_client().get(ADMIN_URL, headers=bearer(token))
    assert (response.status_code, response.get_json()['code']) == (401, 'invalid_token')


def test_unsigned_alg_none_token_is_401(app):
    token = pyjwt.encode({'sub': '1', 'role': 'admin', 'type': 'access', 'jti': 'x', 'fresh': False}, '',
                         algorithm='none')
    assert app.test_client().get(ADMIN_URL, headers=bearer(token)).status_code == 401


def test_legacy_routes_answer_401_in_their_own_format(app):
    assert app.test_client().get('/bays').get_json() == {'error': 'Debes iniciar sesión para acceder a este recurso'}


def test_logout_revokes_the_token(app):
    token = _token(app)
    client = app.test_client()
    assert client.get('/auth/me', headers=bearer(token)).status_code == 200
    assert client.post('/auth/logout', headers=bearer(token)).status_code == 200
    response = client.get(USER_URL, headers=bearer(token))
    assert (response.status_code, response.get_json()['code']) == (401, 'token_revoked')


def test_deactivated_user_loses_access_immediately(app):
    from infrastructure.persistence.models import User
    token = _token(app)
    with app.app_context():
        db.session.query(User).filter_by(email='client@test.com').update({'status': 'inactive'})
        db.session.commit()
        db.session.remove()
    assert app.test_client().get(USER_URL, headers=bearer(token)).status_code == 401


def test_token_with_a_stale_role_is_rejected(app):
    from infrastructure.persistence.models import User
    token = _token(app)
    with app.app_context():
        db.session.query(User).filter_by(email='client@test.com').update({'role': 'mechanic'})
        db.session.commit()
        db.session.remove()
    assert app.test_client().get(USER_URL, headers=bearer(token)).status_code == 401


# --- RBAC -------------------------------------------------------------------------

def test_admin_endpoint_accepts_only_admin(app, admin_user):
    client = app.test_client()
    assert client.get(ADMIN_URL, headers=bearer(_token(app, admin_user))).status_code == 200
    for email in ('client@test.com', 'mechanic@test.com', 'owner@test.com'):
        response = client.get(ADMIN_URL, headers=bearer(_token(app, email)))
        assert (response.status_code, response.get_json()['code']) == (403, 'forbidden')


def test_user_endpoint_accepts_only_client(app, admin_user):
    client = app.test_client()
    assert client.get(USER_URL, headers=bearer(_token(app))).status_code == 200
    assert client.get(USER_URL, headers=bearer(_token(app, admin_user))).status_code == 403


@pytest.mark.parametrize('method, url, body', [
    ('post', '/bays', {'bay_number': 'Bahia 9'}),
    ('post', '/api/v1/services', {}),
    ('get', '/businesses/mechanics', None),
])
def test_management_endpoints_reject_client_and_mechanic(app, method, url, body):
    client = app.test_client()
    for email in ('client@test.com', 'mechanic@test.com'):
        response = getattr(client, method)(url, json=body, headers=bearer(_token(app, email)))
        assert response.status_code == 403


def test_app_refuses_to_start_without_a_signing_key():
    class NoKey(TestConfig):
        JWT_SECRET_KEY = None
    with pytest.raises(RuntimeError, match='JWT_SECRET_KEY'):
        create_app(NoKey)
