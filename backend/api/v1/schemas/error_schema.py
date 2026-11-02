"""Esquema del formato unico de error de /api/v1 y ayudas para documentar ejemplos."""

from marshmallow import Schema, fields


class ApiErrorSchema(Schema):
    code = fields.String(required=True, metadata={
        'description': 'Stable, machine-readable error identifier in snake_case.', 'example': 'not_found'})
    message = fields.String(required=True, metadata={
        'description': 'Human-readable explanation of the error.', 'example': 'Service 42 was not found'})
    details = fields.Raw(allow_none=True, metadata={
        'description': 'Extra context, e.g. validation errors per field. May be null.',
        'example': {'service_id': 42}})


def error_example(code, message, details=None):
    return {'code': code, 'message': message, 'details': details}


UNAUTHORIZED_EXAMPLE = error_example('unauthorized', 'Authentication required: log in via POST /api/auth/login')
FORBIDDEN_EXAMPLE = error_example('forbidden', 'Your role is not allowed to perform this action',
                                  {'required_roles': ['owner', 'admin'], 'your_role': 'client'})
