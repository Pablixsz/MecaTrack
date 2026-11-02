"""
CRUD del catalogo de servicios en /api/v1/services.

- Lectura (GET) publica: el catalogo se muestra antes de iniciar sesion.
- Escritura (POST/PUT/DELETE) solo para 'owner' y 'admin', con el mismo
  middleware de roles que usan las rutas antiguas.
- A diferencia de DELETE /services (borrado logico), aqui DELETE elimina el
  registro y responde 409 si el servicio ya tiene citas: borrarlo dejaria
  citas huerfanas. Para retirarlo del catalogo se usa PUT con status='inactive'.

Los docstrings de cada metodo son publicos: la primera linea es el `summary`
de OpenAPI y el resto la `description`. Por eso van en ingles.
"""

from flask.views import MethodView
from flask_smorest import Blueprint

from api.auth import role_required
from api.deps import actor, container
from api.v1.schemas.error_schema import FORBIDDEN_EXAMPLE, UNAUTHORIZED_EXAMPLE, ApiErrorSchema, error_example
from api.v1.schemas.service_schema import ServiceInputSchema, ServiceQuerySchema, ServiceSchema

blp = Blueprint('Services', __name__, description='Workshop service catalog: list, read, create, replace and delete.')

WRITE_ROLES = ('owner', 'admin')
# role_required va por fuera de los decoradores de smorest: primero se valida
# la sesion (401/403) y despues el cuerpo (422). functools.wraps conserva la
# documentacion OpenAPI que smorest guarda en la funcion.
AUTH_DOC = {'security': [{'bearerAuth': []}]}

# --- Ejemplos para Swagger UI ------------------------------------------------

SERVICE_EXAMPLE = {
    'service_id': 1, 'business_id': 1, 'service_name': 'Cambio de aceite',
    'description': 'Cambio de aceite y filtro', 'estimated_duration_minutes': 45,
    'base_price': 80000, 'status': 'active',
}
INPUT_EXAMPLE = {
    'service_name': 'Cambio de pastillas de freno',
    'description': 'Reemplazo de pastillas delanteras y revision de discos',
    'estimated_duration_minutes': 90, 'base_price': 150000, 'status': 'active',
}
CREATED_EXAMPLE = {**INPUT_EXAMPLE, 'service_id': 3, 'business_id': 1}
NOT_FOUND_EXAMPLE = error_example('not_found', 'Service 42 was not found', {'service_id': 42})
VALIDATION_EXAMPLE = error_example('validation_error', 'The request body is invalid', {
    'service_name': ['Shorter than minimum length 2.'],
    'base_price': ['Must be greater than or equal to 0 and less than or equal to 100000000.'],
})
DUPLICATE_EXAMPLE = error_example('duplicate_service_name', "A service named 'Cambio de aceite' already exists",
                                  {'service_name': 'Cambio de aceite', 'existing_service_id': 1})
HAS_APPOINTMENTS_EXAMPLE = error_example('service_has_appointments',
                                         'Service 1 has 3 appointment(s) and cannot be deleted',
                                         {'service_id': 1, 'appointments': 3})


def _error(status, description, example):
    # Se crea un decorador nuevo por endpoint: apispec modifica el dict de la
    # respuesta al procesarlo y no debe compartirse entre operaciones.
    return blp.alt_response(status, schema=ApiErrorSchema, description=description, example=example)


def not_found():
    return _error(404, 'No service exists with the given id.', NOT_FOUND_EXAMPLE)


def invalid_body():
    return _error(422, 'The body failed validation; `details` lists the errors per field.', VALIDATION_EXAMPLE)


def unauthorized():
    return _error(401, 'Missing or invalid token. Log in with POST /api/auth/login first.', UNAUTHORIZED_EXAMPLE)


def forbidden():
    return _error(403, 'The token role is not `owner` or `admin`.', FORBIDDEN_EXAMPLE)


def duplicate():
    return _error(409, 'Another service of the workshop already uses that name (case-insensitive).',
                  DUPLICATE_EXAMPLE)


# Las reglas (nombre unico por taller, 404, 409 si tiene citas) viven en
# application.catalog.services.ServiceCatalogService; sus errores de dominio
# se traducen al formato unico en api/errors.py (handle_domain_error).

# --- Endpoints -------------------------------------------------------------------

@blp.route('')
class ServiceCollection(MethodView):

    @blp.arguments(ServiceQuerySchema, location='query')
    @blp.response(200, ServiceSchema(many=True), description='The services matching the filter, ordered by id.',
                  example=[SERVICE_EXAMPLE, {**SERVICE_EXAMPLE, 'service_id': 2, 'service_name': 'Alineacion y balanceo',
                                             'description': 'Alineacion de llantas y balanceo',
                                             'estimated_duration_minutes': 60, 'base_price': 120000}])
    @_error(422, 'Invalid query parameter.', error_example(
        'validation_error', 'The request body is invalid', {'status': ['Must be one of: active, inactive, all.']}))
    def get(self, query):
        """List services

        Returns the service catalog ordered by id. By default only active
        services are returned; use `status=all` to include inactive ones.
        Public endpoint, no authentication required.
        """
        status = None if query['status'] == 'all' else query['status']
        return container().catalog.list_by_status(status)

    @role_required(*WRITE_ROLES)
    @blp.arguments(ServiceInputSchema, example=INPUT_EXAMPLE)
    @blp.response(201, ServiceSchema, description='The service was created; the body is the stored resource.',
                  example=CREATED_EXAMPLE)
    @invalid_body()
    @unauthorized()
    @forbidden()
    @duplicate()
    @blp.doc(**AUTH_DOC)
    def post(self, data):
        """Create a service

        Adds a new service to the catalog of the authenticated user's
        workshop. `service_name`, `estimated_duration_minutes` and
        `base_price` are required; `status` defaults to `active`.
        Requires an `owner` or `admin` token (from POST /api/auth/login).
        """
        return container().catalog.create(actor(), data)


@blp.route('/<int:service_id>', parameters=[{'in': 'path', 'name': 'service_id',
                                             'description': 'Identifier of the service.', 'example': 1}])
class ServiceItem(MethodView):

    @blp.response(200, ServiceSchema, description='The requested service.', example=SERVICE_EXAMPLE)
    @not_found()
    def get(self, service_id):
        """Get a service

        Returns a single service by its id, whether it is active or inactive.
        Public endpoint, no authentication required.
        """
        return container().catalog.get(service_id)

    @role_required(*WRITE_ROLES)
    @blp.arguments(ServiceInputSchema, example={**INPUT_EXAMPLE, 'base_price': 165000})
    @blp.response(200, ServiceSchema, description='The service after the replacement.',
                  example={**CREATED_EXAMPLE, 'base_price': 165000})
    @not_found()
    @invalid_body()
    @unauthorized()
    @forbidden()
    @duplicate()
    @blp.doc(**AUTH_DOC)
    def put(self, data, service_id):
        """Replace a service

        Replaces every editable field of the service. This is a full
        replacement, not a partial update: omitted optional fields go back to
        their defaults. To retire a service that already has appointments,
        send `status: inactive`. Requires an `owner` or `admin` token.
        """
        return container().catalog.replace(service_id, data)

    @role_required(*WRITE_ROLES)
    @blp.response(204, description='The service was deleted. The response has no body.')
    @not_found()
    @unauthorized()
    @forbidden()
    @_error(409, 'The service is referenced by appointments and cannot be deleted.', HAS_APPOINTMENTS_EXAMPLE)
    @blp.doc(**AUTH_DOC)
    def delete(self, service_id):
        """Delete a service

        Permanently deletes a service that has never been booked. If any
        appointment references it the API answers 409, because deleting it
        would orphan those appointments; deactivate it with PUT
        (`status: inactive`) instead. Requires an `owner` or `admin` token.
        """
        container().catalog.delete(service_id)
