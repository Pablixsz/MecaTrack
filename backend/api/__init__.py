"""
Capa api (adaptador de entrada HTTP). Las rutas solo traducen HTTP <-> casos
de uso: leen el request, llaman al servicio de aplicacion del contenedor y
serializan la respuesta. Las reglas de negocio viven en application/domain.

- api/legacy: rutas que usa el frontend (errores {"error": "..."}).
- api/v1:     API REST documentada con OpenAPI (errores {"code","message","details"}).
"""

from time import time

from flask import jsonify, request

from api.auth import jwt
from api.errors import error_response, handle_domain_error, is_api_request
from api.rate_limit import limiter
from domain.shared.errors import DomainError

LEGACY_BLUEPRINTS = (
    ('api.legacy.auth_routes', 'auth_bp', '/auth'),
    ('api.legacy.vehicle_routes', 'vehicle_bp', '/vehicles'),
    ('api.legacy.service_routes', 'service_bp', '/services'),
    ('api.legacy.business_routes', 'business_bp', '/businesses'),
    ('api.legacy.bay_routes', 'bay_bp', '/bays'),
    ('api.legacy.part_routes', 'part_bp', '/parts'),
    ('api.legacy.appointment_routes', 'appointment_bp', '/appointments'),
    ('api.legacy.payment_routes', 'payment_bp', '/payments'),
    ('api.legacy.service_tracking_routes', 'tracking_bp', '/tracking'),
    ('api.jwt_routes', 'jwt_auth_bp', '/api/auth'),
    ('api.jwt_routes', 'rbac_bp', '/api/rbac'),
)


# Security (OWASP API8): these answers are always JSON and never include a stack trace.
LEGACY_HTTP_ERRORS = {
    413: 'La petición es demasiado grande',
    429: 'Demasiadas peticiones, intenta de nuevo más tarde',
    500: 'Ocurrió un error inesperado',
}


def _http_error_handler(legacy_message):
    def handler(error):
        if is_api_request():
            response = error_response(error)
        else:
            response = jsonify({'error': legacy_message})
            response.status_code = error.code
        if error.code == 429 and 'Retry-After' not in response.headers:
            response.headers['Retry-After'] = str(max(1, int(limiter.current_limit.reset_at - time())))
        return response
    return handler


def register_api(app):
    from importlib import import_module

    jwt.init_app(app)
    limiter.init_app(app)
    app.register_error_handler(DomainError, handle_domain_error)

    for module, name, prefix in LEGACY_BLUEPRINTS:
        app.register_blueprint(getattr(import_module(module), name), url_prefix=prefix)

    # API v1 (flask-smorest). Va despues de los blueprints antiguos: el spec
    # documenta /auth/login y /auth/logout a partir de sus reglas.
    from api.openapi import init_api
    init_api(app)

    @app.after_request
    def security_headers(response):
        # The API only serves JSON: browsers must not sniff it into executable HTML.
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        # Swagger UI needs its CDN scripts; everything else is JSON and loads nothing.
        if request.path != '/docs':
            response.headers['Content-Security-Policy'] = "default-src 'none'; frame-ancestors 'none'"
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    for status, message in LEGACY_HTTP_ERRORS.items():
        app.register_error_handler(status, _http_error_handler(message))
