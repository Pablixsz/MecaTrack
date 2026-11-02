from importlib import import_module

from flask import Flask
from flask_cors import CORS

import bootstrap
from config import Config
from infrastructure.persistence.extensions import db, migrate


def create_app(config_object=Config):
    """
    App factory. Une las piezas de la arquitectura hexagonal:
    configuracion -> extensiones de infraestructura -> composition root
    (bootstrap.py) -> adaptador HTTP (api).
    """
    app = Flask(__name__)
    app.config.from_object(config_object)
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
    app.run(host='127.0.0.1', port=5000, debug=True)
