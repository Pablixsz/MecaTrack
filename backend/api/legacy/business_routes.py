from flask import Blueprint, jsonify, request

from api.auth import role_required
from api.deps import actor, container
from api.legacy import json_body, missing_field, paginate
from api.legacy.auth_routes import REGISTER_FIELDS

business_bp = Blueprint('businesses', __name__)


@business_bp.route('/mine', methods=['GET'])
@role_required('owner')
def get_my_business():
    return jsonify(_serialize_business(container().business.get_owned(actor()))), 200


@business_bp.route('/mine', methods=['PUT'])
@role_required('owner')
def update_my_business():
    container().business.update_owned(actor(), json_body())
    return jsonify({'message': 'Negocio actualizado'}), 200


@business_bp.route('/mechanics', methods=['POST'])
@role_required('owner')
def create_mechanic():
    """El dueño crea la cuenta del mecanico (el registro publico solo crea clientes)."""
    data = json_body()
    error = missing_field(data, REGISTER_FIELDS)
    if error:
        return error
    mechanic = container().auth.register(data, role='mechanic')
    return jsonify({'message': 'Mecánico creado', 'user_id': mechanic.user_id}), 201


@business_bp.route('/clients', methods=['GET'])
@role_required('owner', 'admin')
def search_clients():
    """Recepcion: busca clientes por nombre, apellido, correo o documento (?q=)."""
    clients = container().auth.search_clients(request.args.get('q') or None)
    return paginate([_serialize_client(c) for c in clients]), 200


@business_bp.route('/clients', methods=['POST'])
@role_required('owner', 'admin')
def create_client():
    """Recepcion: registra a un cliente nuevo que llega o llama al taller."""
    data = json_body()
    error = missing_field(data, REGISTER_FIELDS)
    if error:
        return error
    client = container().auth.register(data, role='client')
    return jsonify({'message': 'Cliente registrado', 'user_id': client.user_id}), 201


@business_bp.route('/mechanics', methods=['GET'])
@role_required('owner', 'admin')
def list_mechanics():
    return jsonify([_serialize_mechanic(m) for m in container().staff.list_mechanics()]), 200


@business_bp.route('/mechanics/<int:user_id>', methods=['PUT'])
@role_required('owner')
def update_mechanic(user_id):
    container().staff.update_mechanic(user_id, json_body())
    return jsonify({'message': 'Mecánico actualizado'}), 200


def _serialize_mechanic(m):
    return {
        'user_id': m.user_id,
        'first_name': m.first_name,
        'last_name': m.last_name,
        'email': m.email,
        'phone': m.phone,
        'status': m.status
    }


def _serialize_client(c):
    return {
        'user_id': c.user_id,
        'first_name': c.first_name,
        'last_name': c.last_name,
        'document_number': c.document_number,
        'email': c.email,
        'phone': c.phone,
        'status': c.status
    }


def _serialize_business(b):
    return {
        'business_id': b.business_id,
        'business_name': b.business_name,
        'tax_id': b.tax_id,
        'address': b.address,
        'business_phone': b.business_phone,
        'business_registration_number': b.business_registration_number,
        'legal_documents_verified': b.legal_documents_verified
    }
