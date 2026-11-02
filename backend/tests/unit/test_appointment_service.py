"""
AppointmentService con TODAS sus dependencias simuladas (unittest.mock).

Demuestra la testabilidad que da la inyeccion por constructor: sin Flask,
sin PostgreSQL y en milisegundos se verifica la orquestacion del caso de
uso (que se asigna, que se guarda, cuando se confirma la transaccion).
"""

from dataclasses import replace
from datetime import datetime
from unittest.mock import call, create_autospec

import pytest

from application.scheduling.services import AppointmentService
from domain.catalog.ports import ServiceRepository, VehicleRepository
from domain.payments.entities import Payment
from domain.payments.ports import PaymentRepository
from domain.scheduling.allocation import ResourceAllocator
from domain.scheduling.entities import AppointmentView
from domain.scheduling.ports import AppointmentRepository
from domain.shared.errors import Conflict, DomainError, InvalidInput, NotFound, PermissionDenied
from domain.shared.ports import UnitOfWork
from tests.unit.factories import (CLIENT, MECHANIC, OTHER_CLIENT, OWNER, START, make_appointment, make_bay,
                                  make_mechanic, make_service, make_vehicle)


@pytest.fixture
def deps():
    deps = {
        'appointments': create_autospec(AppointmentRepository, instance=True),
        'vehicles': create_autospec(VehicleRepository, instance=True),
        'services': create_autospec(ServiceRepository, instance=True),
        'allocator': create_autospec(ResourceAllocator, instance=True),
        'payments': create_autospec(PaymentRepository, instance=True),
        'uow': create_autospec(UnitOfWork, instance=True),
    }
    deps['vehicles'].get.return_value = make_vehicle()
    deps['services'].get.return_value = make_service()
    deps['allocator'].find_bay_and_mechanic.return_value = (make_bay(), make_mechanic())
    # El repositorio devuelve la cita con el id que asigna la BD.
    deps['appointments'].add.side_effect = lambda appointment: replace(appointment, appointment_id=7)
    deps['appointments'].count_active_by_client.return_value = 0
    deps['payments'].list_by_appointment.return_value = []
    return deps


@pytest.fixture
def service(deps):
    return AppointmentService(**deps)  # inyeccion por constructor


def test_book_assigns_resources_creates_two_payments_and_commits_once(service, deps):
    booking = service.book(CLIENT, vehicle_id=10, service_id=1, scheduled_start=START, payment_method='card')

    end = datetime(2030, 1, 10, 9, 45)  # inicio + 45 min del servicio
    deps['allocator'].find_bay_and_mechanic.assert_called_once_with(1, START, end)

    [stored] = deps['appointments'].add.call_args.args
    assert (stored.client_user_id, stored.bay_id, stored.mechanic_user_id) == (CLIENT.user_id, 1, MECHANIC.user_id)
    assert (stored.scheduled_end, stored.status) == (end, 'pending')

    assert deps['payments'].add.call_args_list == [
        call(Payment(appointment_id=7, payment_type='deposit', payment_method='card', amount=24000)),
        call(Payment(appointment_id=7, payment_type='balance', payment_method='card', amount=56000)),
    ]
    deps['uow'].commit.assert_called_once_with()
    assert (booking.appointment.appointment_id, booking.deposit_amount, booking.balance_amount) == (7, 24000, 56000)


def test_book_without_availability_raises_conflict_and_writes_nothing(service, deps):
    deps['allocator'].find_bay_and_mechanic.return_value = (None, None)

    with pytest.raises(Conflict) as error:
        service.book(CLIENT, 10, 1, START)

    assert error.value.message == 'No hay disponibilidad de bahía o mecánico en ese horario'
    deps['appointments'].add.assert_not_called()
    deps['payments'].add.assert_not_called()
    deps['uow'].commit.assert_not_called()


@pytest.mark.parametrize('setup, message', [
    (lambda d: setattr(d['vehicles'].get, 'return_value', make_vehicle(owner_user_id=OTHER_CLIENT.user_id)),
     'Vehículo inválido'),
    (lambda d: setattr(d['vehicles'].get, 'return_value', None), 'Vehículo inválido'),
    (lambda d: setattr(d['services'].get, 'return_value', make_service(status='inactive')), 'Servicio inválido'),
], ids=['vehiculo_de_otro_cliente', 'vehiculo_inexistente', 'servicio_inactivo'])
def test_book_validates_before_looking_for_resources(service, deps, setup, message):
    setup(deps)
    with pytest.raises(InvalidInput, match=message):
        service.book(CLIENT, 10, 1, START)
    deps['allocator'].find_bay_and_mechanic.assert_not_called()


def test_book_rejects_unknown_payment_method(service, deps):
    with pytest.raises(InvalidInput, match='Método de pago inválido'):
        service.book(CLIENT, 10, 1, START, payment_method='bitcoin')
    deps['uow'].commit.assert_not_called()


def test_cancel_marks_cancelled_and_saves(service, deps):
    deps['appointments'].get.return_value = make_appointment(status='confirmed')
    service.cancel(CLIENT, 7)
    [saved] = deps['appointments'].save.call_args.args
    assert saved.status == 'cancelled'
    deps['uow'].commit.assert_called_once_with()


@pytest.mark.parametrize('actor, status, error', [
    (OTHER_CLIENT, 'pending', PermissionDenied),
    (CLIENT, 'completed', InvalidInput),
    (CLIENT, 'cancelled', InvalidInput),
])
def test_cancel_rules(service, deps, actor, status, error):
    deps['appointments'].get.return_value = make_appointment(status=status)
    with pytest.raises(error):
        service.cancel(actor, 7)
    deps['appointments'].save.assert_not_called()


def test_mechanic_cannot_change_status_of_an_appointment_assigned_to_someone_else(service, deps):
    deps['appointments'].get.return_value = make_appointment(mechanic_user_id=555)
    with pytest.raises(PermissionDenied):
        service.change_status(MECHANIC, 7, 'completed')
    deps['uow'].commit.assert_not_called()


def test_autospec_mocks_enforce_the_port_contract(deps):
    """
    Un Mock() comun acepta cualquier metodo y ocultaria errores de interfaz.
    create_autospec solo acepta lo que declara el puerto y con su firma.
    """
    with pytest.raises(AttributeError):
        deps['appointments'].find_all()  # AppointmentRepository no declara find_all
    with pytest.raises(TypeError):
        deps['payments'].add()  # add(payment) exige un argumento


# --- Recepcion: agendar a nombre de un cliente -------------------------------------

def test_admin_books_on_behalf_of_the_client(service, deps):
    from tests.unit.factories import ADMIN
    booking = service.book(ADMIN, 10, 1, START, client_user_id=CLIENT.user_id)

    [stored] = deps['appointments'].add.call_args.args
    assert stored.client_user_id == CLIENT.user_id  # la cita es del cliente, no del admin
    assert booking.deposit_amount == 24000
    deps['uow'].commit.assert_called_once_with()


def test_admin_must_say_which_client(service, deps):
    from tests.unit.factories import ADMIN
    with pytest.raises(InvalidInput, match='Indica el cliente'):
        service.book(ADMIN, 10, 1, START)
    deps['appointments'].add.assert_not_called()


def test_admin_cannot_book_a_vehicle_of_another_client(service, deps):
    from tests.unit.factories import ADMIN
    with pytest.raises(InvalidInput, match='Vehículo inválido'):
        service.book(ADMIN, 10, 1, START, client_user_id=OTHER_CLIENT.user_id)


def test_a_client_cannot_book_on_behalf_of_someone_else(service, deps):
    with pytest.raises(PermissionDenied):
        service.book(CLIENT, 10, 1, START, client_user_id=OTHER_CLIENT.user_id)
    deps['allocator'].find_bay_and_mechanic.assert_not_called()


# --- Mutation testing: argumentos, mensajes y casos sin cubrir ---------------

def test_book_looks_up_the_requested_vehicle_and_service(service, deps):
    service.book(CLIENT, 10, 1, START)
    deps['vehicles'].get.assert_called_once_with(10)
    deps['services'].get.assert_called_once_with(1)


def test_book_defaults_to_cash_and_pending_payments(service, deps):
    service.book(CLIENT, 10, 1, START)
    payments = [c.args[0] for c in deps['payments'].add.call_args_list]
    assert [p.payment_method for p in payments] == ['cash', 'cash']
    assert [p.status for p in payments] == ['pending', 'pending']


def test_book_stores_vehicle_service_and_start(service, deps):
    service.book(CLIENT, 10, 1, START)
    [stored] = deps['appointments'].add.call_args.args
    assert (stored.vehicle_id, stored.service_id, stored.scheduled_start) == (10, 1, START)


def test_book_conflict_has_a_stable_code(service, deps):
    deps['allocator'].find_bay_and_mechanic.return_value = (make_bay(), None)
    with pytest.raises(Conflict) as error:
        service.book(CLIENT, 10, 1, START)
    assert error.value.code == 'no_availability'


def test_book_lists_the_valid_payment_methods_in_the_error(service):
    with pytest.raises(InvalidInput) as error:
        service.book(CLIENT, 10, 1, START, payment_method='bitcoin')
    assert error.value.message == "Método de pago inválido, debe ser uno de: ('cash', 'card', 'transfer')"


def test_booking_for_someone_else_explains_why_it_is_denied(service):
    with pytest.raises(PermissionDenied) as error:
        service.book(CLIENT, 10, 1, START, client_user_id=OTHER_CLIENT.user_id)
    assert error.value.message == 'No puedes agendar a nombre de otro cliente'


def test_a_client_may_name_himself_when_booking(service, deps):
    service.book(CLIENT, 10, 1, START, client_user_id=CLIENT.user_id)
    assert deps['appointments'].add.call_args.args[0].client_user_id == CLIENT.user_id


def test_list_for_delegates_with_the_actor(service, deps):
    deps['appointments'].list_views_for.return_value = ['view']
    assert service.list_for(CLIENT) == ['view']
    deps['appointments'].list_views_for.assert_called_once_with(CLIENT)


def test_get_returns_the_view_for_a_participant(service, deps):
    view = AppointmentView(appointment=make_appointment(), client_name='Laura', mechanic_name='Andres',
                           vehicle_plate='ABC123', service_name='Aceite', bay_number='Bahia 1')
    deps['appointments'].get_view.return_value = view
    assert service.get(CLIENT, 7) is view
    deps['appointments'].get_view.assert_called_once_with(7)


def test_get_unknown_appointment_is_not_found(service, deps):
    deps['appointments'].get_view.return_value = None
    with pytest.raises(NotFound) as error:
        service.get(CLIENT, 404)
    assert error.value.message == 'Cita no encontrada'


def test_get_denies_someone_else(service, deps):
    view = AppointmentView(appointment=make_appointment(), client_name=None, mechanic_name=None,
                           vehicle_plate=None, service_name=None, bay_number=None)
    deps['appointments'].get_view.return_value = view
    with pytest.raises(PermissionDenied) as error:
        service.get(OTHER_CLIENT, 7)
    assert error.value.message == 'No tienes permiso para ver esta cita'


def test_change_status_saves_the_new_status_and_commits(service, deps):
    appointment = make_appointment()
    deps['appointments'].get.return_value = appointment

    assert service.change_status(MECHANIC, 7, 'in_progress') is appointment

    deps['appointments'].get.assert_called_once_with(7)
    assert appointment.status == 'in_progress'
    deps['appointments'].save.assert_called_once_with(appointment)
    deps['uow'].commit.assert_called_once_with()


def test_change_status_rejects_unknown_status(service, deps):
    deps['appointments'].get.return_value = make_appointment()
    with pytest.raises(InvalidInput) as error:
        service.change_status(OWNER, 7, 'lost')
    assert error.value.message.startswith('Estado inválido, debe ser uno de: ')
    deps['appointments'].save.assert_not_called()


def test_managers_change_status_of_any_appointment(service, deps):
    deps['appointments'].get.return_value = make_appointment(mechanic_user_id=555)
    assert service.change_status(OWNER, 7, 'completed').status == 'completed'


def test_change_status_denial_explains_why(service, deps):
    deps['appointments'].get.return_value = make_appointment(mechanic_user_id=555)
    with pytest.raises(PermissionDenied) as error:
        service.change_status(MECHANIC, 7, 'completed')
    assert error.value.message == 'No tienes permiso para modificar esta cita'


def test_change_status_of_unknown_appointment_is_not_found(service, deps):
    deps['appointments'].get.return_value = None
    with pytest.raises(NotFound) as error:
        service.change_status(OWNER, 404, 'completed')
    assert error.value.message == 'Cita no encontrada'


def test_cancel_loads_the_requested_appointment(service, deps):
    deps['appointments'].get.return_value = make_appointment()
    service.cancel(CLIENT, 7)
    deps['appointments'].get.assert_called_once_with(7)


@pytest.mark.parametrize('actor, status, message', [
    (OTHER_CLIENT, 'pending', 'No tienes permiso para cancelar esta cita'),
    (CLIENT, 'completed', 'Esta cita ya no se puede cancelar'),
])
def test_cancel_errors_explain_why(service, deps, actor, status, message):
    deps['appointments'].get.return_value = make_appointment(status=status)
    with pytest.raises(DomainError) as error:
        service.cancel(actor, 7)
    assert error.value.message == message


# --- OWASP API6: flujos sensibles ----------------------------------------------

def test_book_is_denied_at_the_active_appointment_limit(service, deps):
    deps['appointments'].count_active_by_client.return_value = 5
    with pytest.raises(Conflict) as error:
        service.book(CLIENT, 10, 1, START)
    assert error.value.code == 'too_many_active_appointments'
    assert error.value.message == 'El cliente ya tiene 5 citas activas'
    deps['appointments'].count_active_by_client.assert_called_once_with(CLIENT.user_id)
    deps['allocator'].find_bay_and_mechanic.assert_not_called()


def test_book_is_allowed_just_below_the_limit(service, deps):
    deps['appointments'].count_active_by_client.return_value = 4
    assert service.book(CLIENT, 10, 1, START).deposit_amount == 24000


def test_reception_counts_the_appointments_of_the_client_not_of_the_admin(service, deps):
    deps['appointments'].count_active_by_client.return_value = 0
    service.book(OWNER, 10, 1, START, client_user_id=CLIENT.user_id)
    deps['appointments'].count_active_by_client.assert_called_once_with(CLIENT.user_id)


def test_confirming_requires_a_paid_deposit(service, deps):
    deps['appointments'].get.return_value = make_appointment()
    deps['payments'].list_by_appointment.return_value = [Payment(appointment_id=7, payment_type='deposit',
                                                                 payment_method='cash', amount=1)]
    with pytest.raises(Conflict) as error:
        service.change_status(OWNER, 7, 'confirmed')
    assert error.value.code == 'deposit_required'
    assert error.value.message == 'La cita solo se confirma con el depósito pagado'
    deps['payments'].list_by_appointment.assert_called_once_with(7)
    deps['appointments'].save.assert_not_called()


def test_a_paid_balance_does_not_replace_the_deposit(service, deps):
    deps['appointments'].get.return_value = make_appointment()
    deps['payments'].list_by_appointment.return_value = [Payment(appointment_id=7, payment_type='balance',
                                                                 payment_method='cash', amount=1, status='completed')]
    with pytest.raises(Conflict):
        service.change_status(OWNER, 7, 'confirmed')


def test_confirming_works_with_a_paid_deposit(service, deps):
    deps['appointments'].get.return_value = make_appointment()
    deps['payments'].list_by_appointment.return_value = [Payment(appointment_id=7, payment_type='deposit',
                                                                 payment_method='cash', amount=1, status='completed')]
    assert service.change_status(OWNER, 7, 'confirmed').status == 'confirmed'
