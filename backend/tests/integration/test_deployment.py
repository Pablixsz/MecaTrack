"""Deployment surface (Lab 8): /health, the frontend served by Flask, proxy awareness and the seed."""

import os
from unittest.mock import patch

from sqlalchemy.exc import OperationalError
from werkzeug.security import check_password_hash

from app import create_app
from config import TestConfig
from infrastructure.persistence.extensions import db
from tests.integration.conftest import PASSWORD

SEED_SQL = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'database', 'seed.sql')


def test_health_is_200_when_the_database_answers(app):
    response = app.test_client().get('/health')
    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok', 'database': 'ok'}


def test_health_is_503_when_the_database_is_down(app):
    down = OperationalError('SELECT 1', {}, Exception('connection refused'))
    with patch.object(db.session, 'execute', side_effect=down):
        response = app.test_client().get('/health')
    assert response.status_code == 503
    body = response.get_json()
    assert body['status'] == 'unavailable'
    # Security: the driver error never reaches the public response.
    assert 'refused' not in response.get_data(as_text=True)


def test_health_needs_no_token_and_is_not_rate_limited(app):
    client = app.test_client()
    with patch.dict(app.config, {'RATELIMIT_DEFAULT': '2 per minute'}):
        assert all(client.get('/health').status_code == 200 for _ in range(5))


def test_frontend_index_is_served_with_its_own_csp(app):
    response = app.test_client().get('/')
    assert response.status_code == 200
    assert response.mimetype == 'text/html'
    assert '<title>' in response.get_data(as_text=True)
    csp = response.headers['Content-Security-Policy']
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "'unsafe-eval'" not in csp


def test_frontend_pages_and_assets_are_served(app):
    client = app.test_client()
    for path in ('/index.html', '/pages/catalogo.html', '/css/styles.css', '/js/api.js'):
        assert client.get(path).status_code == 200, path


def test_frontend_does_not_shadow_the_api(app):
    client = app.test_client()
    assert client.get('/pages/does-not-exist.html').status_code == 404
    # API routes keep their strict JSON policy.
    assert client.get('/services').headers['Content-Security-Policy'] == "default-src 'none'; frame-ancestors 'none'"
    assert client.get('/api/nope').status_code == 404


def test_frontend_blocks_path_traversal(app):
    client = app.test_client()
    for path in ('/js/../../backend/.env', '/pages/..%2f..%2fbackend%2fconfig.py', '/css/%2e%2e/%2e%2e/README.md'):
        assert client.get(path).status_code == 404, path


def test_behind_a_proxy_https_and_client_ip_come_from_forwarded_headers():
    class ProxiedConfig(TestConfig):
        PROXY_FIX_HOPS = 1

    response = create_app(ProxiedConfig).test_client().get(
        '/health', headers={'X-Forwarded-Proto': 'https', 'X-Forwarded-For': '203.0.113.7'})
    assert 'max-age' in response.headers['Strict-Transport-Security']


def test_without_proxy_forwarded_headers_are_ignored(app):
    response = app.test_client().get('/health', headers={'X-Forwarded-Proto': 'https'})
    assert 'Strict-Transport-Security' not in response.headers


def test_seed_sql_loads_on_the_migrated_schema_and_its_users_can_log_in(app):
    from infrastructure.persistence.models import User
    with app.app_context():
        table_names = ', '.join(t.name for t in db.metadata.sorted_tables)
        db.session.execute(db.text(f'TRUNCATE {table_names} RESTART IDENTITY CASCADE'))
        with open(SEED_SQL, encoding='utf-8') as seed_file:
            db.session.connection().exec_driver_sql(seed_file.read())
        db.session.commit()
        users = {u.email: u for u in db.session.query(User).all()}
        db.session.remove()

    assert {u.role for u in users.values()} == {'owner', 'mechanic', 'client', 'admin'}
    assert all(check_password_hash(u.password_hash, PASSWORD) for u in users.values())
    response = app.test_client().post('/api/auth/login',
                                      json={'email': 'laura.cliente@gmail.com', 'password': PASSWORD})
    assert response.status_code == 200
    assert response.get_json()['role'] == 'client'
