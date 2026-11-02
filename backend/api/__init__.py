"""
Capa api (adaptador de entrada HTTP). Las rutas solo traducen HTTP <-> casos
de uso: leen el request, llaman al servicio de aplicacion del contenedor y
serializan la respuesta. Las reglas de negocio viven en application/domain.

- api/legacy: rutas que usa el frontend (errores {"error": "..."}).
- api/v1:     API REST documentada con OpenAPI (errores {"code","message","details"}).
"""

from api.auth import jwt
from api.errors import handle_domain_error
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


def register_api(app):
    from importlib import import_module

    jwt.init_app(app)
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
        return response
