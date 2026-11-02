"""POST /api/auth/login and the two role-protected endpoints that demonstrate RBAC."""

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import create_access_token

from api.auth import role_required
from api.deps import container
from api.errors import ApiError
from api.legacy import json_body

jwt_auth_bp = Blueprint('jwt_auth', __name__)
rbac_bp = Blueprint('rbac', __name__)


@jwt_auth_bp.route('/login', methods=['POST'])
def login():
    data = json_body()
    if not data.get('email') or not data.get('password'):
        raise ApiError(400, 'bad_request', 'email and password are required')

    user = container().auth.authenticate(data['email'], data['password'])
    token = create_access_token(identity=str(user.user_id), additional_claims={'role': user.role})
    return jsonify({
        'access_token': token,
        'token_type': 'Bearer',
        'expires_in': int(current_app.config['JWT_ACCESS_TOKEN_EXPIRES'].total_seconds()),
        'user_id': user.user_id,
        'role': user.role,
    }), 200


@rbac_bp.route('/admin', methods=['GET'])
@role_required('admin')
def admin_only():
    return jsonify({'message': 'Hello admin', 'required_role': 'admin'}), 200


@rbac_bp.route('/user', methods=['GET'])
@role_required('client')
def user_only():
    return jsonify({'message': 'Hello user', 'required_role': 'client'}), 200
