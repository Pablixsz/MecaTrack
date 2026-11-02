"""PaymentService con repositorios, unit of work y RELOJ simulados."""

from unittest.mock import create_autospec

import pytest

from application.payments.services import PaymentService
from domain.payments.ports import PaymentRepository
from domain.scheduling.ports import AppointmentRepository
from domain.shared.errors import DomainError, InvalidInput, NotFound, PermissionDenied
from domain.shared.ports import Clock, UnitOfWork
from tests.unit.factories import CLIENT, OTHER_CLIENT, OWNER, make_appointment, make_payment


@pytest.fixture
def deps(fixed_now):
    clock = create_autospec(Clock, instance=True)
    clock.now.return_value = fixed_now
    return {
        'payments': create_autospec(PaymentRepository, instance=True),
        'appointments': create_autospec(AppointmentRepository, instance=True),
        'uow': create_autospec(UnitOfWork, instance=True),
        'clock': clock,
    }


@pytest.fixture
def service(deps):
    return PaymentService(**deps)


def test_paying_the_deposit_completes_it_and_confirms_the_appointment(service, deps, fixed_now):
    deps['payments'].get.return_value = make_payment(payment_type='deposit')
    deps['appointments'].get.return_value = make_appointment(status='pending')

    payment = service.pay(CLIENT, 21, 'transfer')

    assert (payment.status, payment.payment_method, payment.paid_at) == ('completed', 'transfer', fixed_now)
    deps['payments'].save.assert_called_once_with(payment)
    [appointment] = deps['appointments'].save.call_args.args
    assert appointment.status == 'confirmed'
    deps['uow'].commit.assert_called_once_with()


def test_paying_the_balance_does_not_touch_the_appointment(service, deps):
    deps['payments'].get.return_value = make_payment(payment_type='balance', payment_method='card')
    deps['appointments'].get.return_value = make_appointment(status='confirmed')

    payment = service.pay(OWNER, 21)  # sin metodo: conserva el original

    assert payment.payment_method == 'card'
    deps['appointments'].save.assert_not_called()
    deps['uow'].commit.assert_called_once_with()


@pytest.mark.parametrize('actor, payment, method, error', [
    (CLIENT, make_payment(status='completed'), None, InvalidInput),
    (CLIENT, make_payment(), 'bitcoin', InvalidInput),
    (OTHER_CLIENT, make_payment(), None, PermissionDenied),
])
def test_invalid_payments_write_nothing(service, deps, actor, payment, method, error):
    deps['payments'].get.return_value = payment
    deps['appointments'].get.return_value = make_appointment()
    with pytest.raises(error):
        service.pay(actor, 21, method)
    deps['payments'].save.assert_not_called()
    deps['uow'].commit.assert_not_called()


def test_unknown_payment_is_not_found(service, deps):
    deps['payments'].get.return_value = None
    with pytest.raises(NotFound):
        service.pay(CLIENT, 404)
    deps['appointments'].get.assert_not_called()


def test_list_checks_that_the_actor_participates(service, deps):
    deps['appointments'].get.return_value = make_appointment()
    deps['payments'].list_by_appointment.return_value = [make_payment()]
    assert len(service.list_for_appointment(CLIENT, 7)) == 1
    with pytest.raises(PermissionDenied):
        service.list_for_appointment(OTHER_CLIENT, 7)


# --- Mutation testing: argumentos, mensajes y casos sin cubrir ---------------

def test_list_reads_the_payments_of_the_requested_appointment(service, deps):
    deps['appointments'].get.return_value = make_appointment()
    payments = [make_payment()]
    deps['payments'].list_by_appointment.return_value = payments

    assert service.list_for_appointment(CLIENT, 7) is payments

    deps['appointments'].get.assert_called_once_with(7)
    deps['payments'].list_by_appointment.assert_called_once_with(7)


def test_list_of_unknown_appointment_is_not_found(service, deps):
    deps['appointments'].get.return_value = None
    with pytest.raises(NotFound) as error:
        service.list_for_appointment(CLIENT, 404)
    assert error.value.message == 'Cita no encontrada'
    deps['payments'].list_by_appointment.assert_not_called()


def test_list_denial_explains_why(service, deps):
    deps['appointments'].get.return_value = make_appointment()
    with pytest.raises(PermissionDenied) as error:
        service.list_for_appointment(OTHER_CLIENT, 7)
    assert error.value.message == 'No tienes permiso para ver estos pagos'
    deps['payments'].list_by_appointment.assert_not_called()


def test_pay_loads_the_payment_and_its_appointment(service, deps):
    deps['payments'].get.return_value = make_payment(appointment_id=7)
    deps['appointments'].get.return_value = make_appointment()

    service.pay(CLIENT, 21)

    deps['payments'].get.assert_called_once_with(21)
    deps['appointments'].get.assert_called_once_with(7)


@pytest.mark.parametrize('actor, payment, method, message', [
    (OTHER_CLIENT, make_payment(), None, 'No tienes permiso para pagar esto'),
    (CLIENT, make_payment(status='completed'), None, 'Este pago ya fue completado'),
    (CLIENT, make_payment(), 'bitcoin', 'Método de pago inválido'),
])
def test_pay_errors_explain_why(service, deps, actor, payment, method, message):
    deps['payments'].get.return_value = payment
    deps['appointments'].get.return_value = make_appointment()
    with pytest.raises(DomainError) as error:
        service.pay(actor, 21, method)
    assert error.value.message == message


def test_unknown_payment_message(service, deps):
    deps['payments'].get.return_value = None
    with pytest.raises(NotFound) as error:
        service.pay(CLIENT, 404)
    assert error.value.message == 'Pago no encontrado'


def test_a_manager_pays_someone_elses_appointment(service, deps):
    deps['payments'].get.return_value = make_payment(payment_type='balance')
    deps['appointments'].get.return_value = make_appointment(client_user_id=555, status='confirmed')
    assert service.pay(OWNER, 21).is_completed


def test_paying_an_already_confirmed_deposit_saves_no_appointment(service, deps):
    deps['payments'].get.return_value = make_payment(payment_type='deposit')
    deps['appointments'].get.return_value = make_appointment(status='confirmed')
    service.pay(CLIENT, 21)
    deps['appointments'].save.assert_not_called()
