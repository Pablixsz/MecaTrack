from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from domain.scheduling.entities import Appointment, AppointmentView
from domain.shared.actor import Actor


class AppointmentRepository(ABC):
    @abstractmethod
    def get(self, appointment_id: int) -> Optional[Appointment]: ...

    @abstractmethod
    def get_view(self, appointment_id: int) -> Optional[AppointmentView]: ...

    @abstractmethod
    def list_views_for(self, actor: Actor) -> list[AppointmentView]:
        """Cliente: sus citas; mecanico: las asignadas; admin/owner: todas."""

    @abstractmethod
    def count_active_by_client(self, client_user_id: int) -> int:
        """Citas del cliente que todavia ocupan bahia y mecanico."""

    @abstractmethod
    def has_blocking_overlap(self, scheduled_start: datetime, scheduled_end: datetime, *,
                             bay_id: Optional[int] = None, mechanic_user_id: Optional[int] = None,
                             exclude_appointment_id: Optional[int] = None) -> bool:
        """True si la bahia (o el mecanico) tiene una cita bloqueante que se solapa."""

    @abstractmethod
    def add(self, appointment: Appointment) -> Appointment: ...

    @abstractmethod
    def save(self, appointment: Appointment) -> None: ...
