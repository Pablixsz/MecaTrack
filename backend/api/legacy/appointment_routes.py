from datetime import datetime

from flask import Blueprint, jsonify

from api.auth import role_required
from api.deps import actor, container
from api.legacy import json_body, missing_field, paginate

appointment_bp = Blueprint('appointments', __name__)


@appointment_bp.route('', methods=['POST'])
@role_required('client', 'owner', 'admin')
def create_appointment():
    """
    El cliente agenda vehiculo + servicio + hora de inicio; en recepcion,
    owner/admin lo hacen a nombre de un cliente (client_user_id). El caso de
    uso asigna bahia y mecanico y genera los pagos (AppointmentService.book).
    """
    data = json_body()
    error = missing_field(data, ['vehicle_id', 'service_id', 'scheduled_start'])
    if error:
        return error

    try:
        scheduled_start = datetime.fromisoformat(data['scheduled_start'])
    except (ValueError, TypeError):
        return jsonify({'error': 'Formato de scheduled_start inválido, usa ISO 8601 (ej. 2026-09-20T09:00:00)'}), 400

    booking = container().appointments.book(actor(), data['vehicle_id'], data['service_id'], scheduled_start,
                                            data.get('payment_method', 'cash'),
                                            client_user_id=data.get('client_user_id'))
    appointment = booking.appointment
    return jsonify({
        'message': 'Cita creada, pendiente de pago de depósito para confirmar',
        'appointment_id': appointment.appointment_id,
        'bay_id': appointment.bay_id,
        'mechanic_user_id': appointment.mechanic_user_id,
        'scheduled_start': appointment.scheduled_start.isoformat(),
        'scheduled_end': appointment.scheduled_end.isoformat(),
        'deposit_amount': booking.deposit_amount,
        'balance_amount': booking.balance_amount
    }), 201


@appointment_bp.route('', methods=['GET'])
@role_required('client', 'mechanic', 'admin', 'owner')
def list_appointments():
    # El adaptador carga las relaciones con joinedload (una consulta, sin N+1).
    return paginate([_serialize_appointment(v) for v in container().appointments.list_for(actor())]), 200


@appointment_bp.route('/<int:appointment_id>', methods=['GET'])
@role_required('client', 'mechanic', 'admin', 'owner')
def get_appointment(appointment_id):
    return jsonify(_serialize_appointment(container().appointments.get(actor(), appointment_id))), 200


@appointment_bp.route('/<int:appointment_id>/status', methods=['PUT'])
@role_required('mechanic', 'admin', 'owner')
def update_status(appointment_id):
    appointment = container().appointments.change_status(actor(), appointment_id, json_body().get('status'))
    return jsonify({'message': 'Estado de la cita actualizado', 'status': appointment.status}), 200


@appointment_bp.route('/<int:appointment_id>', methods=['DELETE'])
@role_required('client')
def cancel_appointment(appointment_id):
    container().appointments.cancel(actor(), appointment_id)
    return jsonify({'message': 'Cita cancelada'}), 200


def _serialize_appointment(view):
    a = view.appointment
    return {
        'appointment_id': a.appointment_id,
        'client_user_id': a.client_user_id,
        'vehicle_id': a.vehicle_id,
        'service_id': a.service_id,
        'bay_id': a.bay_id,
        'mechanic_user_id': a.mechanic_user_id,
        'scheduled_start': a.scheduled_start.isoformat(),
        'scheduled_end': a.scheduled_end.isoformat(),
        'status': a.status,
        'client_name': view.client_name,
        'mechanic_name': view.mechanic_name,
        'vehicle_plate': view.vehicle_plate,
        'service_name': view.service_name,
        'bay_number': view.bay_number
    }
