"""ResourceAllocator (servicio de dominio) con puertos simulados."""

from unittest.mock import create_autospec

import pytest

from domain.catalog.ports import BayRepository
from domain.identity.ports import UserRepository
from domain.scheduling.allocation import ResourceAllocator
from domain.scheduling.ports import AppointmentRepository
from tests.unit.factories import START, make_bay, make_mechanic

END = START.replace(minute=45)


@pytest.fixture
def ports():
    bays = create_autospec(BayRepository, instance=True)
    users = create_autospec(UserRepository, instance=True)
    appointments = create_autospec(AppointmentRepository, instance=True)
    bays.list_by_business.return_value = [make_bay(bay_id=1), make_bay(bay_id=2, bay_number='Bahia 2')]
    users.list_mechanics.return_value = [make_mechanic(user_id=2), make_mechanic(user_id=8)]
    return bays, users, appointments


def busy(bays=(), mechanics=()):
    """Simula has_blocking_overlap: ocupados los ids indicados."""
    def _overlap(start, end, *, bay_id=None, mechanic_user_id=None, exclude_appointment_id=None):
        return bay_id in bays or mechanic_user_id in mechanics
    return _overlap


def test_picks_the_first_free_bay_and_mechanic(ports):
    bays, users, appointments = ports
    appointments.has_blocking_overlap.side_effect = busy(bays={1}, mechanics={2})

    bay, mechanic = ResourceAllocator(bays, users, appointments).find_bay_and_mechanic(1, START, END)

    assert (bay.bay_id, mechanic.user_id) == (2, 8)
    bays.list_by_business.assert_called_once_with(1, only_available=True)
    users.list_mechanics.assert_called_once_with(only_active=True)


def test_without_a_free_bay_mechanics_are_not_even_queried(ports):
    bays, users, appointments = ports
    appointments.has_blocking_overlap.side_effect = busy(bays={1, 2})

    assert ResourceAllocator(bays, users, appointments).find_bay_and_mechanic(1, START, END) == (None, None)
    users.list_mechanics.assert_not_called()


def test_a_free_bay_is_useless_without_a_free_mechanic(ports):
    bays, users, appointments = ports
    appointments.has_blocking_overlap.side_effect = busy(mechanics={2, 8})
    assert ResourceAllocator(bays, users, appointments).find_bay_and_mechanic(1, START, END) == (None, None)


# --- Mutation testing: los argumentos exactos llegan a los puertos ------------

def test_bay_lookup_forwards_the_slot_and_the_excluded_appointment(ports):
    bays, users, appointments = ports
    appointments.has_blocking_overlap.return_value = False

    bay = ResourceAllocator(bays, users, appointments).find_available_bay(1, START, END, exclude_appointment_id=7)

    assert bay.bay_id == 1
    appointments.has_blocking_overlap.assert_called_once_with(START, END, bay_id=1, exclude_appointment_id=7)


def test_mechanic_lookup_forwards_the_slot_and_the_excluded_appointment(ports):
    bays, users, appointments = ports
    appointments.has_blocking_overlap.return_value = False

    mechanic = ResourceAllocator(bays, users, appointments).find_available_mechanic(START, END, exclude_appointment_id=7)

    assert mechanic.user_id == 2
    appointments.has_blocking_overlap.assert_called_once_with(START, END, mechanic_user_id=2, exclude_appointment_id=7)


def test_lookups_default_to_no_excluded_appointment(ports):
    bays, users, appointments = ports
    appointments.has_blocking_overlap.return_value = False
    allocator = ResourceAllocator(bays, users, appointments)

    allocator.find_available_bay(1, START, END)
    allocator.find_available_mechanic(START, END)

    assert [c.kwargs['exclude_appointment_id'] for c in appointments.has_blocking_overlap.call_args_list] == [None, None]


def test_bay_and_mechanic_search_forwards_every_argument(ports):
    bays, users, appointments = ports
    appointments.has_blocking_overlap.return_value = False

    ResourceAllocator(bays, users, appointments).find_bay_and_mechanic(9, START, END, exclude_appointment_id=7)

    bays.list_by_business.assert_called_once_with(9, only_available=True)
    appointments.has_blocking_overlap.assert_any_call(START, END, bay_id=1, exclude_appointment_id=7)
    appointments.has_blocking_overlap.assert_any_call(START, END, mechanic_user_id=2, exclude_appointment_id=7)


def test_no_resources_at_all_returns_none(ports):
    bays, users, appointments = ports
    bays.list_by_business.return_value = []
    users.list_mechanics.return_value = []
    allocator = ResourceAllocator(bays, users, appointments)

    assert allocator.find_available_bay(1, START, END) is None
    assert allocator.find_available_mechanic(START, END) is None
