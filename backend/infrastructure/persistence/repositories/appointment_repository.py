from sqlalchemy.orm import joinedload

from domain.scheduling.entities import BLOCKING_STATUSES, Appointment, AppointmentView
from domain.scheduling.ports import AppointmentRepository
from infrastructure.persistence.extensions import db
from infrastructure.persistence.models.appointment_model import Appointment as AppointmentRow
from infrastructure.persistence.repositories.base_repository import SqlAlchemyRepository

# Relaciones que se cargan en la MISMA consulta (JOIN) al listar citas.
# Sin esto, serializar N citas dispararia hasta 5*N consultas extra (N+1).
_VIEW_OPTIONS = (
    joinedload(AppointmentRow.client),
    joinedload(AppointmentRow.mechanic),
    joinedload(AppointmentRow.vehicle),
    joinedload(AppointmentRow.service),
    joinedload(AppointmentRow.bay),
)


def _full_name(user):
    return f'{user.first_name} {user.last_name}' if user else None


class SqlAlchemyAppointmentRepository(SqlAlchemyRepository, AppointmentRepository):
    model, entity, pk = AppointmentRow, Appointment, 'appointment_id'

    def _to_view(self, row):
        if row is None:
            return None
        return AppointmentView(
            appointment=self.to_entity(row),
            client_name=_full_name(row.client),
            mechanic_name=_full_name(row.mechanic),
            vehicle_plate=row.vehicle.license_plate if row.vehicle else None,
            service_name=row.service.service_name if row.service else None,
            bay_number=row.bay.bay_number if row.bay else None,
        )

    def get_view(self, appointment_id):
        row = (AppointmentRow.query.options(*_VIEW_OPTIONS)
               .filter(AppointmentRow.appointment_id == appointment_id).first())
        return self._to_view(row)

    def list_views_for(self, actor):
        query = AppointmentRow.query.options(*_VIEW_OPTIONS)
        if actor.is_client:
            query = query.filter(AppointmentRow.client_user_id == actor.user_id)
        elif actor.is_mechanic:
            query = query.filter(AppointmentRow.mechanic_user_id == actor.user_id)
        return [self._to_view(row) for row in query.order_by(AppointmentRow.scheduled_start.desc())]

    def count_active_by_client(self, client_user_id):
        return AppointmentRow.query.filter(AppointmentRow.client_user_id == client_user_id,
                                           AppointmentRow.status.in_(BLOCKING_STATUSES)).count()

    def has_blocking_overlap(self, scheduled_start, scheduled_end, *, bay_id=None, mechanic_user_id=None,
                             exclude_appointment_id=None):
        """
        Misma regla que domain.scheduling.rules.overlaps, resuelta en SQL:
        existente.inicio < nuevo.fin y nuevo.inicio < existente.fin.
        """
        query = AppointmentRow.query.filter(
            AppointmentRow.status.in_(BLOCKING_STATUSES),
            AppointmentRow.scheduled_start < scheduled_end,
            AppointmentRow.scheduled_end > scheduled_start,
        )
        if bay_id is not None:
            query = query.filter(AppointmentRow.bay_id == bay_id)
        if mechanic_user_id is not None:
            query = query.filter(AppointmentRow.mechanic_user_id == mechanic_user_id)
        if exclude_appointment_id:
            query = query.filter(AppointmentRow.appointment_id != exclude_appointment_id)
        return db.session.query(query.exists()).scalar()
