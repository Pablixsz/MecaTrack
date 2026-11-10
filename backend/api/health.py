"""
GET /health: liveness + readiness in one endpoint.

200 when the database answers, 503 when it does not, so a container or a PaaS
never sends traffic to an instance that cannot serve it. It needs no token and
is exempt from rate limiting because orchestrators call it every few seconds.
"""

from flask import Blueprint, current_app, jsonify

from api.deps import container
from api.rate_limit import limiter

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
@limiter.exempt
def health():
    version = current_app.config['APP_VERSION']
    if container().health.is_healthy():
        return jsonify({'status': 'ok', 'database': 'ok', 'version': version}), 200
    return jsonify({'status': 'unavailable', 'database': 'unreachable', 'version': version}), 503
