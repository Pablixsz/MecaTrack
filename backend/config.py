import os
from datetime import timedelta

from dotenv import load_dotenv

# Carga backend/.env aunque el proceso se lance desde otra carpeta
# (por ejemplo, flask db upgrade desde la raiz o los scripts de scripts/).
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Orígenes del frontend que pueden llamar a la API.
# Incluye 127.0.0.1 y localhost en 5500 (python -m http.server / Live Server)
# y 5501 (Live Server cuando el 5500 está ocupado). Se puede cambiar con
# CORS_ORIGINS="http://host:puerto,http://otro:puerto".
DEFAULT_CORS_ORIGINS = ','.join(
    f'http://{host}:{port}' for host in ('127.0.0.1', 'localhost') for port in (5500, 5501)
)


def normalize_database_url(url):
    """
    Render, Railway and Heroku hand out 'postgres://...', a scheme SQLAlchemy 2.0 no longer
    accepts (it only knows 'postgresql://'). Only the scheme changes; the rest stays as is.
    """
    if url and url.startswith('postgres://'):
        return 'postgresql://' + url[len('postgres://'):]
    return url


class Config:
    # Informative only (Flask 3 removed FLASK_ENV): 'production' in the container.
    APP_ENV = os.environ.get('FLASK_ENV', 'development')
    # Git commit baked into the image by CI (Dockerfile ARG); /health reports it so a deploy can be verified.
    APP_VERSION = os.environ.get('APP_VERSION', 'dev')
    SECRET_KEY = os.environ.get('SECRET_KEY')
    # Security: the signing key comes only from the environment (create_app refuses to start
    # without it) and tokens travel in the Authorization header, so there is no CSRF surface.
    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY')
    JWT_TOKEN_LOCATION = ['headers']
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(seconds=int(os.environ.get('JWT_ACCESS_TOKEN_EXPIRES_SECONDS', 900)))
    # Security (OWASP API4): caps on request size and rate. The in-memory store assumes one
    # server process; point RATELIMIT_STORAGE_URI at Redis when running several.
    MAX_CONTENT_LENGTH = 1024 * 1024
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '300 per minute')
    RATELIMIT_STORAGE_URI = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
    RATELIMIT_HEADERS_ENABLED = True
    # Its own name: the limiter must not overwrite the Retry-After of the AI quota (429).
    RATELIMIT_HEADER_RETRY_AFTER = 'X-RateLimit-Retry-After'
    LOGIN_RATE_LIMIT = os.environ.get('LOGIN_RATE_LIMIT', '5 per minute')
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get('DATABASE_URL'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Managed databases close idle connections: test each one before use instead of failing a request.
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True}
    # Number of reverse proxies in front of the app (Render: 1). With 0 the request is trusted as is;
    # with 1, X-Forwarded-For/Proto give the real client IP (rate limits) and HTTPS (HSTS).
    PROXY_FIX_HOPS = int(os.environ.get('PROXY_FIX_HOPS', 0))
    # Static frontend served by Flask itself (one public URL). Set to '' to disable it.
    FRONTEND_DIR = os.environ.get('FRONTEND_DIR',
                                  os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend'))
    CORS_ORIGINS = [o.strip() for o in os.environ.get('CORS_ORIGINS', DEFAULT_CORS_ORIGINS).split(',') if o.strip()]

    # OpenAPI / flask-smorest
    API_TITLE = 'MecaTrack API'
    API_VERSION = 'v1'
    OPENAPI_VERSION = '3.0.3'
    OPENAPI_URL_PREFIX = '/'
    OPENAPI_JSON_PATH = 'openapi.json'          # -> GET /openapi.json
    OPENAPI_SWAGGER_UI_PATH = '/docs'           # -> GET /docs
    OPENAPI_SWAGGER_UI_URL = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.17.14/'
    OPENAPI_SWAGGER_UI_CONFIG = {'displayRequestDuration': True, 'tryItOutEnabled': True}

    # Asistente IA (/api/v1/ai). La key y el modelo vienen SOLO de backend/.env;
    # sin ellos el endpoint responde 503 (ai_not_configured).
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_MODEL = os.environ.get('GEMINI_MODEL')
    AI_TIMEOUT_SECONDS = float(os.environ.get('AI_TIMEOUT_SECONDS', 20))
    AI_MAX_RETRIES = int(os.environ.get('AI_MAX_RETRIES', 2))
    AI_RETRY_BASE_SECONDS = float(os.environ.get('AI_RETRY_BASE_SECONDS', 1))
    AI_MAX_CALLS_PER_HOUR = int(os.environ.get('AI_MAX_CALLS_PER_HOUR', 20))

    # Datos abiertos (datos.gov.co y geoportal del DANE): resiliencia y almacenamiento.
    MARKET_DATA_DIR = os.environ.get('MARKET_DATA_DIR',
                                     os.path.join(os.path.dirname(os.path.abspath(__file__)), 'var', 'market_data'))
    MARKET_HTTP_TIMEOUT_SECONDS = float(os.environ.get('MARKET_HTTP_TIMEOUT_SECONDS', 30))
    MARKET_MAX_RETRIES = int(os.environ.get('MARKET_MAX_RETRIES', 3))
    MARKET_RETRY_BASE_SECONDS = float(os.environ.get('MARKET_RETRY_BASE_SECONDS', 0.5))
    MARKET_RETRY_MAX_SECONDS = float(os.environ.get('MARKET_RETRY_MAX_SECONDS', 8))
    CIRCUIT_FAILURE_THRESHOLD = int(os.environ.get('CIRCUIT_FAILURE_THRESHOLD', 3))
    CIRCUIT_RECOVERY_SECONDS = float(os.environ.get('CIRCUIT_RECOVERY_SECONDS', 30))
    # Base de datos.gov.co. Solo se cambia para la DEMOSTRACION CONTROLADA del circuit
    # breaker (scripts/generar_evidencia.sh la apunta a un host .invalid).
    MARKET_SOCRATA_BASE_URL = os.environ.get('MARKET_SOCRATA_BASE_URL', 'https://www.datos.gov.co/resource')
    # Opcional: token de Socrata (sube el limite de peticiones). Sin token tambien funciona.
    SOCRATA_APP_TOKEN = os.environ.get('SOCRATA_APP_TOKEN') or None


def _default_test_database_url():
    """
    Si no se define TEST_DATABASE_URL, reutiliza las credenciales de
    DATABASE_URL pero apuntando a la base 'taller_mecanico_test'.
    """
    from sqlalchemy.engine import make_url
    base = normalize_database_url(os.environ.get('DATABASE_URL'))
    if not base:
        return None
    return make_url(base).set(database='taller_mecanico_test').render_as_string(hide_password=False)


class TestConfig(Config):
    """
    Configuracion de pruebas: usa SIEMPRE una base aparte (TEST_DATABASE_URL),
    nunca la de desarrollo. tests/conftest.py se niega a correr si el nombre
    de la base no termina en '_test'.
    """
    TESTING = True
    SECRET_KEY = 'test-secret-key'
    JWT_SECRET_KEY = 'test-only-jwt-signing-key-with-enough-length'
    # Practically unlimited: test_owasp_controls lowers the login limit where it is under test.
    RATELIMIT_DEFAULT = '100000 per minute'
    LOGIN_RATE_LIMIT = '100000 per minute'
    # El LLM se simula en las pruebas: nunca se usa la key real ni hay esperas.
    GEMINI_API_KEY = 'test-key'
    GEMINI_MODEL = 'test-model'
    AI_RETRY_BASE_SECONDS = 0
    MARKET_RETRY_BASE_SECONDS = 0
    SQLALCHEMY_DATABASE_URI = normalize_database_url(os.environ.get('TEST_DATABASE_URL')) or _default_test_database_url()
