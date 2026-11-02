"""
Pruebas de integracion: recorren la API real (Flask + SQLAlchemy +
PostgreSQL) de punta a punta, sin mocks.
"""

from sqlalchemy import event

from infrastructure.persistence.extensions import db


def _create_vehicle(client, plate='ABC123'):
    response = client.post('/vehicles', json={
        'license_plate': plate, 'brand': 'Mazda', 'model': '3', 'year': 2020,
        'vehicle_type': 'car', 'fuel_type': 'gasoline', 'transmission_type': 'automatic'
    })
    assert response.status_code == 201, response.get_json()
    return response.get_json()['vehicle_id']


def _book(client, vehicle_id, start):
    return client.post('/appointments', json={
        'vehicle_id': vehicle_id, 'service_id': 1, 'scheduled_start': start
    })


def test_login_and_role_based_access(app, login):
    anonymous = app.test_client()

    # Credenciales invalidas y rutas protegidas sin sesion
    bad = anonymous.post('/api/auth/login', json={'email': 'client@test.com', 'password': 'mala'})
    assert bad.status_code == 401
    assert anonymous.get('/appointments').status_code == 401

    # Un cliente autenticado no puede gestionar bahias (solo owner/admin/mecanico)
    client = login('client@test.com')
    assert client.get('/auth/me').get_json()['role'] == 'client'
    assert client.get('/bays').status_code == 403
    assert client.post('/bays', json={'bay_number': 'Bahia 9'}).status_code == 403

    # El dueño si puede crear y listar bahias de su negocio
    owner = login('owner@test.com')
    assert owner.post('/bays', json={'bay_number': 'Bahia 2', 'has_elevator': True}).status_code == 201
    bays = owner.get('/bays').get_json()
    assert [b['bay_number'] for b in bays] == ['Bahia 1', 'Bahia 2']

    # Logout revoca el token
    assert client.post('/auth/logout').status_code == 200
    assert client.get('/appointments').status_code == 401


def test_booking_flow_assigns_resources_and_deposit_confirms(app, login):
    client = login('client@test.com')
    vehicle_id = _create_vehicle(client)

    # El motor de agendamiento asigna bahia y mecanico y calcula el fin
    response = _book(client, vehicle_id, '2030-01-10T09:00:00')
    assert response.status_code == 201, response.get_json()
    body = response.get_json()
    assert body['bay_id'] == 1 and body['mechanic_user_id'] == 2
    assert body['scheduled_end'] == '2030-01-10T09:45:00'
    assert (body['deposit_amount'], body['balance_amount']) == (24000, 56000)  # 30% / 70%

    # Se generan los dos pagos; pagar el deposito confirma la cita
    payments = client.get(f"/payments/appointment/{body['appointment_id']}").get_json()
    assert [p['payment_type'] for p in payments] == ['deposit', 'balance']
    assert client.post(f"/payments/{payments[0]['payment_id']}/pay", json={}).status_code == 200
    assert client.get(f"/appointments/{body['appointment_id']}").get_json()['status'] == 'confirmed'

    # Vista global del dueño: los datos de las relaciones vienen en la respuesta
    for hour in ('10', '11', '12'):
        assert _book(client, vehicle_id, f'2030-01-10T{hour}:00:00').status_code == 201

    owner = login('owner@test.com')
    selects = []

    def count_select(conn, cursor, statement, *args):
        if statement.lstrip().upper().startswith('SELECT'):
            selects.append(statement)

    with app.app_context():
        engine = db.engine
    event.listen(engine, 'before_cursor_execute', count_select)
    try:
        appointments = owner.get('/appointments').get_json()
    finally:
        event.remove(engine, 'before_cursor_execute', count_select)

    assert len(appointments) == 4
    assert appointments[0]['client_name'] == 'Laura Test'
    assert appointments[0]['mechanic_name'] == 'Andres Test'
    assert appointments[0]['vehicle_plate'] == 'ABC123'
    assert appointments[0]['bay_number'] == 'Bahia 1'
    # joinedload: 1 SELECT para el usuario de la sesion + 1 para las citas con
    # sus relaciones. Sin joinedload serian ~5 consultas extra por cita (N+1).
    assert len(selects) <= 2, selects


def test_scheduling_conflict_returns_409_and_cancel_frees_slot(app, login):
    client = login('client@test.com')
    vehicle_id = _create_vehicle(client)

    first = _book(client, vehicle_id, '2030-02-01T09:00:00')
    assert first.status_code == 201

    # Solo hay 1 bahia y 1 mecanico: 09:30 se solapa con 09:00-09:45
    overlap = _book(client, vehicle_id, '2030-02-01T09:30:00')
    assert overlap.status_code == 409

    # Justo al terminar la anterior ([inicio, fin) no se solapa)
    assert _book(client, vehicle_id, '2030-02-01T09:45:00').status_code == 201

    # Al cancelar la primera cita, la franja de las 09:00 vuelve a estar libre
    appointment_id = first.get_json()['appointment_id']
    assert client.delete(f'/appointments/{appointment_id}').status_code == 200
    assert _book(client, vehicle_id, '2030-02-01T09:00:00').status_code == 201

    # Con la bahia en mantenimiento ya no hay disponibilidad
    owner = login('owner@test.com')
    assert owner.put('/bays/1', json={'status': 'under_maintenance'}).status_code == 200
    assert _book(client, vehicle_id, '2030-02-01T15:00:00').status_code == 409
