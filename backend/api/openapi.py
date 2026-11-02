"""
API REST versionada (/api/v1) documentada con OpenAPI 3 via flask-smorest.

Solo los blueprints registrados con `api.register_blueprint` aparecen en la
especificacion; las rutas antiguas del frontend quedan intactas.

- Especificacion JSON: GET /openapi.json
- Swagger UI:          GET /docs
"""

from flask_smorest import Api as SmorestApi

from api.errors import error_response, is_api_request
from api.v1.schemas.error_schema import ApiErrorSchema

API_DESCRIPTION = """
REST API of **MecaTrack**, a booking and vehicle-tracking system for a car repair workshop.

* **Errors** always use the same JSON body: `{"code": "...", "message": "...", "details": ...}`.
* **Authentication** is a JWT Bearer token. Call `POST /api/auth/login`, then send
  `Authorization: Bearer <access_token>` (Swagger UI: **Authorize**). Tokens are short-lived.
* **Roles**: reading the catalog is public; creating, replacing or deleting services
  requires the `owner` or `admin` role, and so does the open-data market panel (`/api/v1/market`).
""".strip()

# Rutas fuera de smorest: se documentan a mano para que aparezcan en Swagger UI.
API_ERROR = {'type': 'object', 'properties': {
    'code': {'type': 'string', 'description': 'Stable error code.', 'example': 'invalid_credentials'},
    'message': {'type': 'string', 'description': 'Readable message.', 'example': 'Credenciales inválidas'},
    'details': {'type': 'object', 'nullable': True, 'description': 'Extra data, if any.', 'example': None}}}


def _error_response(description, code, message):
    return {'description': description, 'content': {'application/json': {
        'schema': API_ERROR, 'example': {'code': code, 'message': message, 'details': None}}}}


def _message_response(description, schema_example):
    return {'description': description, 'content': {'application/json': {
        'schema': {'type': 'object'}, 'example': schema_example}}}


NO_TOKEN = _error_response('Missing, expired or invalid token.', 'unauthorized',
                           'Authentication required: log in via POST /api/auth/login')
WRONG_ROLE = _error_response('The role of the token is not allowed.', 'forbidden',
                             'Your role is not allowed to perform this action')

AUTH_PATHS = {
    '/api/auth/login': {'post': {
        'tags': ['Auth'],
        'summary': 'Log in',
        'description': 'Returns a short-lived JWT access token with the user role as a claim. '
                       'Send it as `Authorization: Bearer <access_token>`.',
        'requestBody': {'required': True, 'content': {'application/json': {
            'schema': {'type': 'object', 'required': ['email', 'password'], 'properties': {
                'email': {'type': 'string', 'format': 'email', 'description': 'Account email.',
                          'example': 'carlos.owner@tallermecanico.com'},
                'password': {'type': 'string', 'format': 'password', 'description': 'Account password.',
                             'example': 'test1234'}}},
            'example': {'email': 'carlos.owner@tallermecanico.com', 'password': 'test1234'}}}},
        'responses': {
            '200': {'description': 'Credentials accepted.', 'content': {'application/json': {
                'schema': {'type': 'object', 'properties': {
                    'access_token': {'type': 'string', 'description': 'Signed JWT.', 'example': 'eyJhbGciOi...'},
                    'token_type': {'type': 'string', 'description': 'Always Bearer.', 'example': 'Bearer'},
                    'expires_in': {'type': 'integer', 'description': 'Lifetime in seconds.', 'example': 900},
                    'user_id': {'type': 'integer', 'description': 'Id of the user.', 'example': 1},
                    'role': {'type': 'string', 'description': 'Role of the user.', 'example': 'owner'}}},
                'example': {'access_token': 'eyJhbGciOi...', 'token_type': 'Bearer', 'expires_in': 900,
                            'user_id': 1, 'role': 'owner'}}}},
            '400': _error_response('Email or password missing.', 'bad_request', 'email and password are required'),
            '401': _error_response('Wrong credentials.', 'invalid_credentials', 'Credenciales inválidas'),
            '403': _error_response('The account is inactive.', 'forbidden', 'Tu cuenta está inactiva'),
        }}},
    '/auth/logout': {'post': {
        'tags': ['Auth'],
        'summary': 'Log out',
        'description': 'Revokes the token used in this request.',
        'security': [{'bearerAuth': []}],
        'responses': {
            '200': _message_response('Token revoked.', {'message': 'Sesión cerrada'}),
            '401': {'description': 'Missing, expired or invalid token.', 'content': {'application/json': {
                'schema': {'type': 'object', 'properties': {'error': {
                    'type': 'string', 'description': 'Error message in Spanish (legacy format of the /auth routes).',
                    'example': 'Debes iniciar sesión para acceder a este recurso'}}},
                'example': {'error': 'Debes iniciar sesión para acceder a este recurso'}}}},
        }}},
    '/api/rbac/admin': {'get': {
        'tags': ['Auth'],
        'summary': 'Admin-only test endpoint',
        'description': 'Demonstrates RBAC: only the `admin` role gets 200.',
        'security': [{'bearerAuth': []}],
        'responses': {'200': _message_response('Allowed.', {'message': 'Hello admin', 'required_role': 'admin'}),
                      '401': NO_TOKEN, '403': WRONG_ROLE}}},
    '/api/rbac/user': {'get': {
        'tags': ['Auth'],
        'summary': 'User-only test endpoint',
        'description': 'Demonstrates RBAC: only the `client` role gets 200.',
        'security': [{'bearerAuth': []}],
        'responses': {'200': _message_response('Allowed.', {'message': 'Hello user', 'required_role': 'client'}),
                      '401': NO_TOKEN, '403': WRONG_ROLE}}},
}


class Api(SmorestApi):
    # Las respuestas de error que smorest agrega solo (p. ej. el 422 de
    # @blp.arguments) usan el formato unico de la API.
    ERROR_SCHEMA = ApiErrorSchema
    # Sin respuesta "default" generica: cada endpoint declara sus errores.
    DEFAULT_ERROR_RESPONSE_NAME = None

    def handle_http_exception(self, error):
        # flask-smorest registra este manejador para TODA la app. Fuera de
        # /api/ se devuelve el error tal cual (comportamiento por defecto de
        # Flask), para no cambiar las respuestas de las rutas antiguas.
        if not is_api_request():
            return error
        return error_response(error)


api = Api()


def init_api(app):
    app.config.setdefault('API_SPEC_OPTIONS', {
        'info': {'description': API_DESCRIPTION,
                 'contact': {'name': 'MecaTrack team - Universidad Manuela Beltran'}},
        'servers': [{'url': 'http://127.0.0.1:5000', 'description': 'Local development server'}],
        'tags': [{'name': 'Auth', 'description': 'JWT login, logout and RBAC test endpoints.'}],
        'components': {'securitySchemes': {'bearerAuth': {
            'type': 'http', 'scheme': 'bearer', 'bearerFormat': 'JWT',
            'description': 'Access token returned by POST /api/auth/login.'}}},
    })
    api.init_app(app)
    # smorest registra siempre el esquema de paginacion; esta API no pagina,
    # asi que se quita para que el spec solo muestre lo que realmente se usa.
    api.spec.components.headers_lazy.pop('PAGINATION', None)
    api.spec.components.schemas.pop('PaginationMetadata', None)

    rules = {rule.rule: rule for rule in app.url_map.iter_rules()}
    for path, operations in AUTH_PATHS.items():
        api.spec.path(rule=rules[path], operations=operations)

    from api.v1.ai import blp as ai_blp
    from api.v1.market import blp as market_blp
    from api.v1.services import blp as services_blp

    api.register_blueprint(services_blp, url_prefix='/api/v1/services')
    api.register_blueprint(ai_blp, url_prefix='/api/v1/ai')
    api.register_blueprint(market_blp, url_prefix='/api/v1/market')
