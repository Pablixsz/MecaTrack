"""
Reglas de la arquitectura hexagonal, verificadas leyendo los imports (AST)
de cada archivo. No necesitan base de datos.

    domain          solo Python estandar; no conoce ninguna otra capa
    application     solo domain (y estandar); nada de Flask/SQLAlchemy/IO
    api             no importa infrastructure (usa los casos de uso del contenedor)
    infrastructure  no importa api ni application
"""

import ast
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
LAYERS = ('domain', 'application', 'api', 'infrastructure')

# Librerias de framework, persistencia o IO prohibidas en el nucleo.
FRAMEWORK_AND_IO = {
    'flask', 'flask_jwt_extended', 'flask_sqlalchemy', 'flask_migrate', 'flask_smorest', 'flask_cors', 'werkzeug',
    'sqlalchemy', 'alembic', 'psycopg2', 'marshmallow', 'webargs', 'apispec',
    'requests', 'httpx', 'urllib3', 'aiohttp', 'google', 'duckdb', 'dotenv',
    'socket', 'http', 'urllib', 'subprocess', 'sqlite3', 'shutil',
}

FORBIDDEN = {
    'domain': FRAMEWORK_AND_IO | {'application', 'api', 'infrastructure', 'bootstrap', 'config', 'app'},
    'application': FRAMEWORK_AND_IO | {'api', 'infrastructure', 'bootstrap', 'config', 'app'},
    'api': {'infrastructure', 'bootstrap'},
    'infrastructure': {'api', 'application', 'bootstrap'},
}


def _imported_roots(path):
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.lineno, node.module.split('.')[0]


def _python_files(layer):
    return sorted((BACKEND / layer).rglob('*.py'))


@pytest.mark.parametrize('layer', LAYERS)
def test_layer_does_not_import_forbidden_modules(layer):
    violations = [
        f'{path.relative_to(BACKEND)}:{lineno} imports {root}'
        for path in _python_files(layer)
        for lineno, root in _imported_roots(path)
        if root in FORBIDDEN[layer]
    ]
    assert not violations, '\n'.join(violations)


def test_domain_only_uses_the_standard_library():
    """Lista blanca: ademas de no usar frameworks, domain no usa NINGUNA libreria externa."""
    stdlib = set(sys.stdlib_module_names)
    external = sorted({
        f'{path.relative_to(BACKEND)} imports {root}'
        for path in _python_files('domain')
        for _, root in _imported_roots(path)
        if root not in stdlib and root != 'domain'
    })
    assert not external, '\n'.join(external)


def test_every_layer_exists_with_code():
    for layer in LAYERS:
        assert len(_python_files(layer)) > 1, f'{layer}/ has no modules'
