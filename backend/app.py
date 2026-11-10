import os
from importlib import import_module

from flask import Flask
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

import bootstrap
from config import Config
from infrastructure.persistence.extensions import db, migrate


def create_app(config_object=Config):
    """
    App factory. Une las piezas de la arquitectura hexagonal:
    configuracion -> extensiones de infraestructura -> composition root
    (bootstrap.py) -> adaptador HTTP (api).
    """
    # static_folder=None: the frontend is served by api/frontend.py, not by Flask's /static.
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_object)
    hops = app.config.get('PROXY_FIX_HOPS', 0)
    if hops:
        # Behind Render's proxy: real client IP for rate limits and HTTPS for HSTS.
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)
    if not app.config.get('JWT_SECRET_KEY'):
        raise RuntimeError('JWT_SECRET_KEY is required: set it in backend/.env (see .env.example)')

    # Security: authentication uses a Bearer header, so CORS never allows credentials (cookies).
    CORS(app, origins=app.config['CORS_ORIGINS'])

    db.init_app(app)
    migrate.init_app(app, db)
    # Registra todas las tablas en db.metadata (Alembic y las pruebas lo usan).
    import_module('infrastructure.persistence.models')

    bootstrap.install(app)

    from api import register_api
    register_api(app)

    return app


# 'flask --app app db ...' (Flask-Migrate) encuentra create_app() solo.
if __name__ == '__main__':
    app = create_app()
    # Security: the Werkzeug debugger allows code execution, so it is opt-in and only for local work.
    app.run(host='127.0.0.1', port=int(os.environ.get('PORT', 5000)), debug=os.environ.get('FLASK_DEBUG') == '1')
