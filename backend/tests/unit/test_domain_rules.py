"""Reglas puras del dominio: sin mocks, sin BD, sin Flask."""

from datetime import datetime

import pytest

from domain.payments.rules import confirms_appointment, split_price
from domain.scheduling.rules import compute_end, ensure_participant, overlaps
from domain.shared.errors import PermissionDenied
from tests.unit.factories import CLIENT, MECHANIC, OTHER_CLIENT, OWNER, make_appointment, make_payment


def at(hour, minute=0):
    return datetime(2030, 1, 10, hour, minute)


@pytest.mark.parametrize('price, expected', [(80000, (24000, 56000)), (99999, (30000, 69999)), (0, (0, 0))])
def test_split_price_is_30_70_and_always_adds_up(price, expected):
    deposit, balance = split_price(price)
    assert (deposit, balance) == expected and deposit + balance == price


@pytest.mark.parametrize('a, b, expected', [
    ((at(9), at(9, 45)), (at(9, 30), at(10)), True),    # cruce parcial
    ((at(9), at(9, 45)), (at(9, 45), at(10)), False),   # [inicio, fin): seguidas no chocan
    ((at(9), at(12)), (at(10), at(11)), True),          # una contiene a la otra
    ((at(9), at(10)), (at(11), at(12)), False),
])
def test_overlaps_uses_half_open_intervals(a, b, expected):
    assert overlaps(*a, *b) is expected
    assert overlaps(*b, *a) is expected  # simetrica


def test_compute_end_adds_service_duration():
    assert compute_end(at(9), 45) == at(9, 45)


def test_only_the_deposit_of_a_pending_appointment_confirms_it():
    assert confirms_appointment(make_payment(payment_type='deposit'), make_appointment(status='pending'))
    assert not confirms_appointment(make_payment(payment_type='balance'), make_appointment(status='pending'))
    assert not confirms_appointment(make_payment(payment_type='deposit'), make_appointment(status='cancelled'))


def test_participants_rule():
    appointment = make_appointment()
    for actor in (CLIENT, MECHANIC, OWNER):
        ensure_participant(actor, appointment, 'x')  # no lanza
    with pytest.raises(PermissionDenied):
        ensure_participant(OTHER_CLIENT, appointment, 'No tienes permiso')


# --- Mutation testing: ensure_participant usa el mensaje indicado -------------

@pytest.mark.parametrize('actor, appointment', [
    (OTHER_CLIENT, make_appointment()),
    (MECHANIC, make_appointment(mechanic_user_id=555)),
])
def test_ensure_participant_raises_with_the_given_message(actor, appointment):
    with pytest.raises(PermissionDenied) as error:
        ensure_participant(actor, appointment, 'sin permiso')
    assert error.value.message == 'sin permiso'
