from flask import Blueprint, jsonify
from flask_jwt_extended import current_user, get_jwt

from api.auth import blocklist, role_required
from api.deps import container
from api.legacy import json_body, missing_field
from domain.shared.actor import ROLES

auth_bp = Blueprint('auth', __name__)

REGISTER_FIELDS = ['first_name', 'last_name', 'document_number', 'email', 'password']


@auth_bp.route('/register', methods=['POST'])
def register():
    data = json_body()
    error = missing_field(data, REGISTER_FIELDS)
    if error:
        return error
    user = container().auth.register(data, role='client')
    return jsonify({'message': 'Usuario registrado exitosamente', 'user_id': user.user_id}), 201


@auth_bp.route('/me', methods=['GET'])
@role_required(*ROLES)
def me():
    return jsonify({
        'user_id': current_user.user_id,
        'first_name': current_user.first_name,
        'last_name': current_user.last_name,
        'email': current_user.email,
        'role': current_user.role
    }), 200


@auth_bp.route('/logout', methods=['POST'])
@role_required(*ROLES)
def logout():
    claims = get_jwt()
    blocklist.revoke(claims['jti'], claims['exp'])
    return jsonify({'message': 'Sesión cerrada'}), 200
