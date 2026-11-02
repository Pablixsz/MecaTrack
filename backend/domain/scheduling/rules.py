"""Reglas puras del agendamiento (sin IO, faciles de probar)."""

from datetime import timedelta

from domain.shared.errors import PermissionDenied

# Security (OWASP API6): one client cannot hoard the workshop's bays and mechanics.
MAX_ACTIVE_APPOINTMENTS = 5


def compute_end(scheduled_start, duration_minutes):
    return scheduled_start + timedelta(minutes=duration_minutes)


def overlaps(start_a, end_a, start_b, end_b):
    """
    Dos franjas [inicio, fin) se solapan si una empieza antes de que la otra
    termine, en ambos sentidos. Justo al terminar una (09:45) puede empezar
    la siguiente sin choque.
    """
    return start_a < end_b and start_b < end_a


def ensure_participant(actor, appointment, message):
    """
    El cliente solo ve sus citas y el mecanico solo las que tiene asignadas;
    admin y owner ven todas.
    """
    if actor.is_client and appointment.client_user_id != actor.user_id:
        raise PermissionDenied(message)
    if actor.is_mechanic and appointment.mechanic_user_id != actor.user_id:
        raise PermissionDenied(message)
