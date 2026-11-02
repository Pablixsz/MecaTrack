"""Casos de uso del agendamiento (bounded context nucleo)."""

from dataclasses import dataclass

from domain.catalog.ports import ServiceRepository, VehicleRepository
from domain.payments.entities import PAYMENT_METHODS, Payment
from domain.payments.ports import PaymentRepository
from domain.payments.rules import split_price
from domain.scheduling.allocation import ResourceAllocator
from domain.scheduling.entities import APPOINTMENT_STATUSES, Appointment
from domain.scheduling.ports import AppointmentRepository
from domain.scheduling.rules import MAX_ACTIVE_APPOINTMENTS, compute_end, ensure_participant
from domain.shared.errors import Conflict, InvalidInput, NotFound, PermissionDenied
from domain.shared.ports import UnitOfWork


@dataclass
class Booking:
    appointment: Appointment
    deposit_amount: int
    balance_amount: int


class AppointmentService:

    def __init__(self, appointments: AppointmentRepository, vehicles: VehicleRepository,
                 services: ServiceRepository, allocator: ResourceAllocator, payments: PaymentRepository,
                 uow: UnitOfWork):
        self._appointments = appointments
        self._vehicles = vehicles
        self._services = services
        self._allocator = allocator
        self._payments = payments
        self._uow = uow

    def book(self, actor, vehicle_id, service_id, scheduled_start, payment_method='cash', client_user_id=None):
        """
        Agenda un vehiculo para un servicio. Lo hace el propio cliente o, en
        recepcion, el administrador/dueño a nombre de un cliente
        (client_user_id). Se calcula el fin con la duracion estimada, se
        asigna automaticamente una bahia y un mecanico libres y se generan los
        pagos de deposito y saldo, todo en una sola transaccion.
        """
        client_id = self._client_for(actor, client_user_id)
        vehicle = self._vehicles.get(vehicle_id)
        if not vehicle or vehicle.owner_user_id != client_id:
            raise InvalidInput('Vehículo inválido')

        if self._appointments.count_active_by_client(client_id) >= MAX_ACTIVE_APPOINTMENTS:
            raise Conflict(f'El cliente ya tiene {MAX_ACTIVE_APPOINTMENTS} citas activas',
                           code='too_many_active_appointments')

        service = self._services.get(service_id)
        if not service or not service.is_bookable:
            raise InvalidInput('Servicio inválido')

        if payment_method not in PAYMENT_METHODS:
            raise InvalidInput(f'Método de pago inválido, debe ser uno de: {PAYMENT_METHODS}')

        scheduled_end = compute_end(scheduled_start, service.estimated_duration_minutes)
        bay, mechanic = self._allocator.find_bay_and_mechanic(service.business_id, scheduled_start, scheduled_end)
        if not bay or not mechanic:
            raise Conflict('No hay disponibilidad de bahía o mecánico en ese horario', code='no_availability')

        appointment = self._appointments.add(Appointment(
            client_user_id=client_id, vehicle_id=vehicle.vehicle_id, service_id=service.service_id,
            bay_id=bay.bay_id, mechanic_user_id=mechanic.user_id,
            scheduled_start=scheduled_start, scheduled_end=scheduled_end, status='pending',
        ))

        deposit, balance = split_price(service.base_price)
        for payment_type, amount in (('deposit', deposit), ('balance', balance)):
            self._payments.add(Payment(appointment_id=appointment.appointment_id, payment_type=payment_type,
                                       payment_method=payment_method, amount=amount, status='pending'))
        self._uow.commit()
        return Booking(appointment, deposit, balance)

    @staticmethod
    def _client_for(actor, client_user_id):
        if actor.is_manager:
            if client_user_id is None:
                raise InvalidInput('Indica el cliente (client_user_id)')
            return client_user_id
        if client_user_id not in (None, actor.user_id):
            raise PermissionDenied('No puedes agendar a nombre de otro cliente')
        return actor.user_id

    def list_for(self, actor):
        return self._appointments.list_views_for(actor)

    def get(self, actor, appointment_id):
        view = self._appointments.get_view(appointment_id)
        if not view:
            raise NotFound('Cita no encontrada')
        ensure_participant(actor, view.appointment, 'No tienes permiso para ver esta cita')
        return view

    def change_status(self, actor, appointment_id, new_status):
        appointment = self._get(appointment_id)
        if actor.is_mechanic and appointment.mechanic_user_id != actor.user_id:
            raise PermissionDenied('No tienes permiso para modificar esta cita')
        if new_status not in APPOINTMENT_STATUSES:
            raise InvalidInput(f'Estado inválido, debe ser uno de: {APPOINTMENT_STATUSES}')
        if new_status == 'confirmed' and not self._deposit_is_paid(appointment_id):
            raise Conflict('La cita solo se confirma con el depósito pagado', code='deposit_required')
        appointment.status = new_status
        self._appointments.save(appointment)
        self._uow.commit()
        return appointment

    def cancel(self, actor, appointment_id):
        appointment = self._get(appointment_id)
        if appointment.client_user_id != actor.user_id:
            raise PermissionDenied('No tienes permiso para cancelar esta cita')
        if not appointment.can_be_cancelled:
            raise InvalidInput('Esta cita ya no se puede cancelar')
        appointment.status = 'cancelled'
        self._appointments.save(appointment)
        self._uow.commit()

    def _deposit_is_paid(self, appointment_id):
        """Security (OWASP API6): staff cannot skip the deposit flow by editing the status."""
        return any(p.is_deposit and p.is_completed for p in self._payments.list_by_appointment(appointment_id))

    def _get(self, appointment_id):
        appointment = self._appointments.get(appointment_id)
        if not appointment:
            raise NotFound('Cita no encontrada')
        return appointment
