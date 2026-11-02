"""
Recepcion de punta a punta: el ADMINISTRADOR registra a un cliente nuevo,
su vehiculo y le agenda una cita (bahia, mecanico y pagos 30/70 automaticos).
"""

import pytest
from werkzeug.security import generate_password_hash

from infrastructure.persistence.extensions import db
from infrastructure.persistence.models import User

NEW_CLIENT = {'first_name': 'Marta', 'last_name': 'Rojas', 'document_number': '5005', 'email': 'marta@test.com',
              'password': 'inicial123', 'phone': '3005550000'}
VEHICLE = {'license_plate': 'MRT555', 'brand': 'Chevrolet', 'model': 'Spark', 'year': 2017, 'vehicle_type': 'car',
           'fuel_type': 'gasoline', 'transmission_type': 'manual'}


@pytest.fixture
def admin(app, login):
    with app.app_context():
        db.session.add(User(first_name='Ana', last_name='Admin', document_number='4004', email='admin@test.com',
                            role='admin', password_hash=generate_password_hash('test1234')))
        db.session.commit()
    return login('admin@test.com')


def test_admin_registers_a_new_client_vehicle_and_books_for_them(app, admin):
    created = admin.post('/businesses/clients', json=NEW_CLIENT)
    assert created.status_code == 201, created.get_json()
    client_id = created.get_json()['user_id']
    assert [c['email'] for c in admin.get('/businesses/clients?q=rojas').get_json()] == ['marta@test.com']

    vehicle = admin.post('/vehicles', json={**VEHICLE, 'client_user_id': client_id})
    assert vehicle.status_code == 201, vehicle.get_json()
    vehicles = admin.get(f'/vehicles?client_user_id={client_id}').get_json()
    assert [v['license_plate'] for v in vehicles] == ['MRT555']

    booking = admin.post('/appointments', json={'vehicle_id': vehicle.get_json()['vehicle_id'], 'service_id': 1,
                                                'scheduled_start': '2030-05-02T10:00:00', 'client_user_id': client_id})
    assert booking.status_code == 201, booking.get_json()
    body = booking.get_json()
    assert (body['bay_id'], body['mechanic_user_id'], body['deposit_amount']) == (1, 2, 24000)

    # La cliente inicia sesion con la contraseña inicial y ve SU cita
    client = app.test_client()
    token = client.post('/api/auth/login', json={'email': 'marta@test.com', 'password': 'inicial123'}).get_json()
    [appointment] = client.get('/appointments', headers={'Authorization': f"Bearer {token['access_token']}"}).get_json()
    assert (appointment['client_name'], appointment['vehicle_plate']) == ('Marta Rojas', 'MRT555')


def test_admin_must_indicate_the_client(admin):
    assert admin.get('/vehicles').get_json() == {'error': 'Indica el cliente (client_user_id)'}
    response = admin.post('/appointments', json={'vehicle_id': 1, 'service_id': 1,
                                                 'scheduled_start': '2030-05-02T10:00:00'})
    assert response.status_code == 400


def test_reception_is_only_for_owner_and_admin(login):
    mechanic = login('mechanic@test.com')
    assert mechanic.get('/businesses/clients').status_code == 403
    assert mechanic.post('/businesses/clients', json=NEW_CLIENT).status_code == 403
    assert mechanic.post('/appointments', json={}).status_code == 403

    client = login('client@test.com')
    assert client.get('/businesses/clients').status_code == 403
    response = client.post('/vehicles', json={**VEHICLE, 'client_user_id': 1})
    assert (response.status_code, response.get_json()) == (403, {'error': 'No puedes operar a nombre de otro cliente'})


def test_duplicate_client_email_is_rejected(admin):
    assert admin.post('/businesses/clients', json={**NEW_CLIENT, 'email': 'client@test.com'}).status_code == 409
