"""
Fixtures de las pruebas de integracion (solo aplican a tests/integration/).

- La base de pruebas se crea con la MISMA migracion de Alembic que usa el
  proyecto (flask_migrate.upgrade), asi las pruebas tambien validan que la
  migracion inicial este correcta.
- Antes de cada prueba se vacian todas las tablas y se cargan datos minimos.
- Por seguridad, si la base configurada no termina en '_test' las pruebas
  abortan: nunca deben tocar la base de desarrollo (taller_mecanico).
"""

import os

import pytest
from sqlalchemy.engine import make_url
from werkzeug.security import generate_password_hash

from app import create_app  # noqa: E402
from config import TestConfig  # noqa: E402
from infrastructure.persistence.extensions import db  # noqa: E402
from flask_migrate import upgrade, downgrade  # noqa: E402

PASSWORD = 'test1234'
MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'migrations')


@pytest.fixture(scope='session')
def app():
    if not TestConfig.SQLALCHEMY_DATABASE_URI:
        pytest.exit('Define TEST_DATABASE_URL (o DATABASE_URL en backend/.env) para correr las pruebas.')

    db_name = make_url(TestConfig.SQLALCHEMY_DATABASE_URI).database
    if not db_name or not db_name.endswith('_test'):
        pytest.exit(f"La base de pruebas debe terminar en '_test' (se recibio '{db_name}'). Abortando.")

    app = create_app(TestConfig)
    with app.app_context():
        # Parte de una base limpia aunque una corrida anterior se haya cortado.
        db.session.execute(db.text('DROP TABLE IF EXISTS alembic_version'))
        db.drop_all()
        db.session.commit()
        upgrade(directory=MIGRATIONS_DIR)

    # No se deja un app context abierto durante las pruebas: cada request del
    # test_client crea el suyo (si no, Flask-Login cachearia el usuario en g).
    yield app

    with app.app_context():
        db.session.remove()
        downgrade(directory=MIGRATIONS_DIR, revision='base')


@pytest.fixture(autouse=True)
def seed(app):
    """Vacia las tablas y carga: owner, mecanico, cliente, negocio, 1 bahia y 1 servicio."""
    from infrastructure.persistence.models import Bay, Business, Service, User

    ctx = app.app_context()
    ctx.push()
    table_names = ', '.join(t.name for t in db.metadata.sorted_tables)
    db.session.execute(db.text(f'TRUNCATE {table_names} RESTART IDENTITY CASCADE'))

    def user(first, email, role, document):
        return User(first_name=first, last_name='Test', document_number=document, email=email,
                    role=role, password_hash=generate_password_hash(PASSWORD))

    owner = user('Carlos', 'owner@test.com', 'owner', '1001')
    mechanic = user('Andres', 'mechanic@test.com', 'mechanic', '1002')
    client = user('Laura', 'client@test.com', 'client', '1003')
    db.session.add_all([owner, mechanic, client])
    db.session.flush()

    business = Business(business_name='MecaTrack Test', tax_id='900-1', address='Calle 1',
                        owner_user_id=owner.user_id)
    db.session.add(business)
    db.session.flush()

    db.session.add_all([
        Bay(business_id=business.business_id, bay_number='Bahia 1'),
        Service(business_id=business.business_id, service_name='Cambio de aceite',
                estimated_duration_minutes=45, base_price=80000),
    ])
    db.session.commit()
    db.session.remove()
    ctx.pop()
    yield


@pytest.fixture(autouse=True)
def block_real_llm(monkeypatch):
    """Ninguna prueba puede llamar al LLM real (el CI no tiene key y cuesta cuota)."""
    from infrastructure.llm import gemini_gateway

    def _fail(*args, **kwargs):
        raise AssertionError('A test tried to call the real LLM; mock gemini_gateway._call_model')

    monkeypatch.setattr(gemini_gateway, '_call_model', _fail)


@pytest.fixture
def login(app):
    """Devuelve un test_client que envia el JWT del usuario indicado en cada peticion."""
    def _login(email):
        client = app.test_client()
        response = client.post('/api/auth/login', json={'email': email, 'password': PASSWORD})
        assert response.status_code == 200, response.get_json()
        client.environ_base['HTTP_AUTHORIZATION'] = f"Bearer {response.get_json()['access_token']}"
        return client
    return _login
