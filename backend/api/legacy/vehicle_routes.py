from flask import Blueprint, jsonify, request

from api.auth import role_required
from api.deps import actor, container
from api.legacy import json_body, missing_field, paginate

vehicle_bp = Blueprint('vehicles', __name__)

REQUIRED_FIELDS = ['license_plate', 'brand', 'model', 'year', 'vehicle_type', 'fuel_type', 'transmission_type']


@vehicle_bp.route('', methods=['POST'])
@role_required('client', 'owner', 'admin')
def create_vehicle():
    """El cliente registra su vehiculo; en recepcion, owner/admin envian client_user_id."""
    data = json_body()
    error = missing_field(data, REQUIRED_FIELDS, allow_falsy=True)
    if error:
        return error
    vehicle = container().vehicles.register(actor(), data, client_user_id=data.get('client_user_id'))
    return jsonify({'message': 'Vehículo registrado', 'vehicle_id': vehicle.vehicle_id}), 201


@vehicle_bp.route('', methods=['GET'])
@role_required('client', 'owner', 'admin')
def list_my_vehicles():
    # Recepcion: owner/admin consultan los vehiculos de un cliente con ?client_user_id=
    client_user_id = request.args.get('client_user_id', type=int)
    vehicles = container().vehicles.list_mine(actor(), client_user_id=client_user_id)
    return paginate([_serialize_vehicle(v) for v in vehicles]), 200


@vehicle_bp.route('/<int:vehicle_id>', methods=['GET'])
@role_required('client', 'mechanic', 'admin', 'owner')
def get_vehicle(vehicle_id):
    return jsonify(_serialize_vehicle(container().vehicles.get(actor(), vehicle_id))), 200


@vehicle_bp.route('/<int:vehicle_id>', methods=['PUT'])
@role_required('client')
def update_vehicle(vehicle_id):
    container().vehicles.update(actor(), vehicle_id, json_body())
    return jsonify({'message': 'Vehículo actualizado'}), 200


@vehicle_bp.route('/<int:vehicle_id>', methods=['DELETE'])
@role_required('client')
def delete_vehicle(vehicle_id):
    container().vehicles.delete(actor(), vehicle_id)
    return jsonify({'message': 'Vehículo eliminado'}), 200


def _serialize_vehicle(v):
    return {
        'vehicle_id': v.vehicle_id,
        'license_plate': v.license_plate,
        'brand': v.brand,
        'model': v.model,
        'year': v.year,
        'color': v.color,
        'vehicle_type': v.vehicle_type,
        'vin': v.vin,
        'engine_displacement': float(v.engine_displacement) if v.engine_displacement is not None else None,
        'mileage': v.mileage,
        'fuel_type': v.fuel_type,
        'transmission_type': v.transmission_type
    }
