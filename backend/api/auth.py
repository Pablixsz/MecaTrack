"""
JWT authentication and role-based access control (HTTP adapter).

Security decisions:
- The role travels as a signed claim, and every request also loads the user from
  the database: a deleted or inactive account, or a role that changed after the
  token was issued, gets 401 instead of keeping access until the token expires.
- Logout revokes the token through its `jti`. The blocklist lives in process
  memory, so it assumes one server process and is lost on restart; the short
  token lifetime bounds the exposure in that case.
"""

from functools import wraps
from time import time

from flask import jsonify
from flask_jwt_extended import JWTManager, get_jwt, verify_jwt_in_request

from api.deps import container
from api.errors import ApiError, error_response, is_api_request

jwt = JWTManager()


class TokenBlocklist:
    """Revoked token ids until their natural expiry; expired ones are pruned on each revocation."""

    def __init__(self, clock=time):
        self._clock = clock
        self._revoked = {}

    def revoke(self, jti, expires_at):
        now = self._clock()
        self._revoked = {key: exp for key, exp in self._revoked.items() if exp > now}
        self._revoked[jti] = expires_at

    def is_revoked(self, jti):
        return jti in self._revoked


blocklist = TokenBlocklist()


def _auth_error(status, code, message, legacy_message, details=None):
    """/api answers {"code","message","details"}; the legacy routes keep {"error": "..."}."""
    if is_api_request():
        return error_response(ApiError(status, code, message, details))
    return jsonify({'error': legacy_message}), status


def _unauthorized(code, message):
    return _auth_error(401, code, message, 'Debes iniciar sesión para acceder a este recurso')


@jwt.user_lookup_loader
def load_user(_header, claims):
    user = container().auth.get_user(int(claims['sub']))
    if not user or not user.is_active or user.role != claims.get('role'):
        return None
    return user


@jwt.token_in_blocklist_loader
def token_is_revoked(_header, claims):
    return blocklist.is_revoked(claims['jti'])


@jwt.unauthorized_loader
def missing_token(_reason):
    return _unauthorized('unauthorized', 'Authentication required: log in via POST /api/auth/login')


@jwt.expired_token_loader
def expired_token(_header, _claims):
    return _unauthorized('token_expired', 'The token has expired: log in again')


@jwt.invalid_token_loader
def invalid_token(_reason):
    # Security: the library's reason is not returned, to give no hints about the signature check.
    return _unauthorized('invalid_token', 'The token is not valid')


@jwt.revoked_token_loader
def revoked_token(_header, _claims):
    return _unauthorized('token_revoked', 'The token was revoked: log in again')


@jwt.user_lookup_error_loader
def user_not_allowed(_header, _claims):
    return _unauthorized('invalid_token', 'The token is not valid')


def role_required(*allowed_roles):
    """
    Protects a route by role.

    Without a valid token -> 401. With a role outside `allowed_roles` -> 403.
    Each route declares its own roles, so access is denied unless listed.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            verify_jwt_in_request()
            role = get_jwt().get('role')
            if role not in allowed_roles:
                return _auth_error(403, 'forbidden', 'Your role is not allowed to perform this action',
                                   'No tienes permiso para realizar esta acción',
                                   {'required_roles': list(allowed_roles), 'your_role': role})
            return f(*args, **kwargs)
        return wrapped
    return decorator
