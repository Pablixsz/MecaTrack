"""
Crea una base DESECHABLE (taller_mecanico_lab7_evidence) con usuarios de prueba para las
capturas de JWT. Nunca toca la base de desarrollo: reutiliza solo las credenciales de
backend/.env. Imprime la URL resultante sin la contrasena y la deja en el archivo indicado.

    backend/venv/bin/python scripts/evidence/seed_jwt_demo.py ARCHIVO_CON_LA_URL
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKEND = os.path.join(ROOT, 'backend')
sys.path.insert(0, BACKEND)

from flask_migrate import upgrade  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

import config  # noqa: E402

DATABASE = 'taller_mecanico_lab7_evidence'
PASSWORD = 'test1234'  # solo para esta base de prueba desechable
USERS = (('Carlos', 'owner@demo.test', 'owner', '9001'), ('Andres', 'mechanic@demo.test', 'mechanic', '9002'),
         ('Laura', 'client@demo.test', 'client', '9003'), ('Ana', 'admin@demo.test', 'admin', '9004'))


def main(url_file):
    base = make_url(os.environ['DATABASE_URL'])
    admin = create_engine(base.set(database='postgres'), isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS {DATABASE}'))
        connection.execute(text(f'CREATE DATABASE {DATABASE}'))
    admin.dispose()

    url = base.set(database=DATABASE).render_as_string(hide_password=False)
    os.environ['DATABASE_URL'] = url
    config.Config.SQLALCHEMY_DATABASE_URI = url

    from app import create_app
    from infrastructure.persistence.extensions import db
    from infrastructure.persistence.models import Bay, Business, Service, User

    app = create_app()
    with app.app_context():
        upgrade(directory=os.path.join(BACKEND, 'migrations'))
        users = {role: User(first_name=first, last_name='Demo', document_number=document, email=email, role=role,
                            password_hash=generate_password_hash(PASSWORD))
                 for first, email, role, document in USERS}
        db.session.add_all(users.values())
        db.session.flush()
        business = Business(business_name='MecaTrack Demo', tax_id='900-9', address='Calle 1',
                            owner_user_id=users['owner'].user_id)
        db.session.add(business)
        db.session.flush()
        db.session.add_all([
            Bay(business_id=business.business_id, bay_number='Bahia 1'),
            Service(business_id=business.business_id, service_name='Cambio de aceite',
                    estimated_duration_minutes=45, base_price=80000),
        ])
        db.session.commit()

    with open(url_file, 'w', encoding='utf-8') as f:
        f.write(url)
    os.chmod(url_file, 0o600)
    print(f'Base lista: {DATABASE}')


if __name__ == '__main__':
    main(sys.argv[1])
