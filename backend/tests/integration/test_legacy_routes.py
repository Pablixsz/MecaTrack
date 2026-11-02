"""
Pruebas de caracterizacion de las rutas antiguas que no tenian cobertura
(negocio, mecanicos, repuestos, servicios, vehiculos, seguimiento y estado
de citas). Se escribieron durante el refactor hexagonal (Guia 6) y se
corrieron primero contra el codigo ORIGINAL (commit 7cca398, 7/7 verdes):
fijan el contrato HTTP que el frontend usa y prueban que no cambio.
"""


def _vehicle(client, plate='XYZ987'):
    response = client.post('/vehicles', json={
        'license_plate': plate, 'brand': 'Renault', 'model': 'Logan', 'year': 2018,
        'vehicle_type': 'car', 'fuel_type': 'gasoline', 'transmission_type': 'manual'})
    assert response.status_code == 201, response.get_json()
    return response.get_json()['vehicle_id']


def _appointment(client, start='2030-03-01T08:00:00'):
    vehicle_id = _vehicle(client)
    response = client.post('/appointments', json={'vehicle_id': vehicle_id, 'service_id': 1,
                                                  'scheduled_start': start})
    assert response.status_code == 201, response.get_json()
    return response.get_json()['appointment_id']


def test_register_validates_and_rejects_duplicates(app):
    anonymous = app.test_client()
    body = {'first_name': 'Ana', 'last_name': 'Ruiz', 'document_number': '2001', 'email': 'ana@test.com',
            'password': 'secreto1'}
    assert anonymous.post('/auth/register', json={**body, 'email': ''}).get_json() == {
        'error': 'El campo email es obligatorio'}
    created = anonymous.post('/auth/register', json=body)
    assert created.status_code == 201 and created.get_json()['user_id'] == 4
    duplicate = anonymous.post('/auth/register', json=body)
    assert (duplicate.status_code, duplicate.get_json()) == (409, {'error': 'Ese correo ya está registrado'})
    same_doc = anonymous.post('/auth/register', json={**body, 'email': 'otra@test.com'})
    assert same_doc.status_code == 409 and 'documento' in same_doc.get_json()['error']
    assert anonymous.post('/api/auth/login', json={'email': 'ana@test.com', 'password': 'secreto1'}).get_json()[
        'role'] == 'client'


def test_owner_manages_business_and_mechanics(app, login):
    owner = login('owner@test.com')
    assert owner.get('/businesses/mine').get_json()['business_name'] == 'MecaTrack Test'
    assert owner.put('/businesses/mine', json={'business_phone': '3001234567', 'tax_id': 'ignorado'}).status_code == 200
    business = owner.get('/businesses/mine').get_json()
    assert (business['business_phone'], business['tax_id']) == ('3001234567', '900-1')

    created = owner.post('/businesses/mechanics', json={
        'first_name': 'Luis', 'last_name': 'Mora', 'document_number': '3001', 'email': 'luis@test.com',
        'password': 'clave123'})
    assert created.status_code == 201
    mechanic_id = created.get_json()['user_id']

    bad = owner.put(f'/businesses/mechanics/{mechanic_id}', json={'status': 'vacaciones'})
    assert bad.status_code == 400
    assert owner.put(f'/businesses/mechanics/{mechanic_id}', json={'status': 'inactive', 'phone': ''}).status_code == 200
    assert owner.put('/businesses/mechanics/3', json={'status': 'inactive'}).status_code == 404  # 3 es cliente

    mechanics = {m['user_id']: m for m in owner.get('/businesses/mechanics').get_json()}
    assert mechanics[mechanic_id]['status'] == 'inactive' and mechanics[2]['status'] == 'active'

    # Un mecanico inactivo no puede iniciar sesion
    inactive = app.test_client().post('/api/auth/login', json={'email': 'luis@test.com', 'password': 'clave123'})
    assert (inactive.status_code, inactive.get_json()['message']) == (403, 'Tu cuenta está inactiva')
    assert login('client@test.com').get('/businesses/mine').status_code == 403


def test_parts_crud_and_inactive_visibility(login):
    owner = login('owner@test.com')
    assert owner.post('/parts', json={'part_name': 'Filtro'}).get_json() == {'error': 'El campo unit_price es obligatorio'}
    part_id = owner.post('/parts', json={'part_name': 'Filtro', 'unit_price': 0, 'stock_quantity': 4}).get_json()['part_id']
    assert owner.put(f'/parts/{part_id}', json={'status': 'roto'}).status_code == 400
    assert owner.put(f'/parts/{part_id}', json={'unit_price': 25000, 'status': 'inactive'}).status_code == 200
    assert owner.put('/parts/999', json={}).status_code == 404

    assert owner.get('/parts').get_json() == []
    [part] = owner.get('/parts?include_inactive=1').get_json()
    assert (part['unit_price'], part['status'], part['stock_quantity']) == (25000, 'inactive', 4)
    # El mecanico no ve los inactivos aunque lo pida
    assert login('mechanic@test.com').get('/parts?include_inactive=1').get_json() == []


def test_legacy_services_crud_uses_soft_delete(app, login):
    owner = login('owner@test.com')
    created = owner.post('/services', json={'service_name': 'Alineacion', 'estimated_duration_minutes': 60,
                                            'base_price': 90000})
    assert created.status_code == 201
    service_id = created.get_json()['service_id']
    assert owner.put(f'/services/{service_id}', json={'status': 'borrado'}).status_code == 400
    assert owner.put(f'/services/{service_id}', json={'base_price': 95000}).status_code == 200
    assert owner.delete(f'/services/{service_id}').get_json() == {'message': 'Servicio desactivado'}
    assert owner.delete('/services/999').status_code == 404

    public = [s['service_id'] for s in app.test_client().get('/services').get_json()]
    managed = {s['service_id']: s for s in owner.get('/services/manage').get_json()}
    assert service_id not in public
    assert (managed[service_id]['status'], managed[service_id]['base_price']) == ('inactive', 95000)


def test_vehicle_ownership_update_and_delete(login):
    client = login('client@test.com')
    vehicle_id = _vehicle(client)
    assert client.post('/vehicles', json={'license_plate': 'XYZ987', 'brand': 'a', 'model': 'b', 'year': 2000,
                                          'vehicle_type': 'car', 'fuel_type': 'diesel',
                                          'transmission_type': 'manual'}).status_code == 409
    assert client.put(f'/vehicles/{vehicle_id}', json={'mileage': 51000, 'license_plate': 'NOP000'}).status_code == 200
    vehicle = client.get(f'/vehicles/{vehicle_id}').get_json()
    assert (vehicle['mileage'], vehicle['license_plate']) == (51000, 'XYZ987')
    assert [v['vehicle_id'] for v in client.get('/vehicles').get_json()] == [vehicle_id]

    # El mecanico tambien puede ver el vehiculo
    assert login('mechanic@test.com').get(f'/vehicles/{vehicle_id}').status_code == 200
    assert client.get('/vehicles/999').status_code == 404

    client.post('/appointments', json={'vehicle_id': vehicle_id, 'service_id': 1,
                                       'scheduled_start': '2030-04-01T08:00:00'})
    blocked = client.delete(f'/vehicles/{vehicle_id}')
    assert blocked.status_code == 409
    free_id = _vehicle(client, plate='FREE01')
    assert client.delete(f'/vehicles/{free_id}').get_json() == {'message': 'Vehículo eliminado'}


def test_tracking_records_steps_and_discounts_stock(login):
    client = login('client@test.com')
    appointment_id = _appointment(client)
    owner = login('owner@test.com')
    part_id = owner.post('/parts', json={'part_name': 'Aceite 5W30', 'unit_price': 40000,
                                         'stock_quantity': 5}).get_json()['part_id']
    mechanic = login('mechanic@test.com')
    url = f'/tracking/appointment/{appointment_id}'

    assert mechanic.post(url, json={'status': 'volando'}).status_code == 400
    assert mechanic.post(url, json={'status': 'in_repair', 'parts_used': [{'part_id': 999}]}).get_json() == {
        'error': 'Repuesto 999 no encontrado'}
    assert mechanic.post(url, json={'status': 'in_repair',
                                    'parts_used': [{'part_id': part_id, 'quantity': 0}]}).status_code == 400
    too_many = mechanic.post(url, json={'status': 'in_repair', 'parts_used': [{'part_id': part_id, 'quantity': 6}]})
    assert too_many.get_json() == {'error': 'No hay stock suficiente de Aceite 5W30'}

    assert mechanic.post(url, json={'status': 'received', 'current_mileage': 50100}).status_code == 201
    ok = mechanic.post(url, json={'status': 'in_repair', 'notes': 'Cambio de aceite',
                                  'parts_used': [{'part_id': part_id, 'quantity': 4}]})
    assert ok.status_code == 201

    records = client.get(url).get_json()
    assert [r['status'] for r in records] == ['received', 'in_repair']
    assert records[1]['parts_used'] == [{'part_id': part_id, 'part_name': 'Aceite 5W30', 'quantity': 4}]
    # Los intentos fallidos no descontaron stock: 5 - 4 = 1
    assert owner.get('/parts').get_json()[0]['stock_quantity'] == 1


def test_appointment_status_permissions_and_cancel_rules(login):
    client = login('client@test.com')
    appointment_id = _appointment(client)

    assert client.put(f'/appointments/{appointment_id}/status', json={'status': 'completed'}).status_code == 403
    mechanic = login('mechanic@test.com')
    assert mechanic.put(f'/appointments/{appointment_id}/status', json={'status': 'lista'}).status_code == 400
    done = mechanic.put(f'/appointments/{appointment_id}/status', json={'status': 'completed'})
    assert done.get_json() == {'message': 'Estado de la cita actualizado', 'status': 'completed'}
    assert mechanic.get(f'/appointments/{appointment_id}').get_json()['mechanic_name'] == 'Andres Test'

    cancel = client.delete(f'/appointments/{appointment_id}')
    assert (cancel.status_code, cancel.get_json()) == (400, {'error': 'Esta cita ya no se puede cancelar'})
    assert client.get('/appointments/999').status_code == 404
    # Pagar dos veces el mismo pago no se permite
    payment_id = client.get(f'/payments/appointment/{appointment_id}').get_json()[0]['payment_id']
    assert client.post(f'/payments/{payment_id}/pay', json={'payment_method': 'bitcoin'}).status_code == 400
    assert client.post(f'/payments/{payment_id}/pay', json={'payment_method': 'card'}).status_code == 200
    assert client.post(f'/payments/{payment_id}/pay', json={}).get_json() == {'error': 'Este pago ya fue completado'}
    paid = client.get(f'/payments/appointment/{appointment_id}').get_json()[0]
    assert (paid['payment_method'], paid['status']) == ('card', 'completed') and paid['paid_at']
