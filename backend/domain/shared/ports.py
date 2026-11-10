"""Puertos transversales a todos los bounded contexts."""

from abc import ABC, abstractmethod
from datetime import datetime


class UnitOfWork(ABC):
    """
    Limite transaccional. Los repositorios agregan cambios pero no los
    confirman: el caso de uso decide cuando termina la unidad de trabajo
    (p. ej. una cita y sus dos pagos quedan en una sola transaccion).
    """

    @abstractmethod
    def commit(self):
        """Confirma; si el almacenamiento rechaza el cambio lanza PersistenceConflict."""

    @abstractmethod
    def rollback(self):
        ...


class HealthProbe(ABC):
    """Checks that a dependency the app cannot work without (the database) answers."""

    @abstractmethod
    def is_healthy(self) -> bool:
        ...


class Clock(ABC):
    @abstractmethod
    def now(self) -> datetime:
        """Fecha y hora actual en UTC, sin zona (como se guarda en la BD)."""
