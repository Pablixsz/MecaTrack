"""DATABASE_URL normalisation: PaaS providers hand out postgres://; the psycopg2 driver is pinned explicitly."""

import pytest

from config import normalize_database_url


@pytest.mark.parametrize('given, expected', [
    ('postgres://u:p@host:5432/db', 'postgresql+psycopg2://u:p@host:5432/db'),
    # SQLAlchemy 2.1 maps a bare postgresql:// to psycopg (v3): the driver must be explicit.
    ('postgresql://u:p@host:5432/db', 'postgresql+psycopg2://u:p@host:5432/db'),
    ('postgresql+psycopg2://u:p@host/db', 'postgresql+psycopg2://u:p@host/db'),
    ('postgresql+psycopg://u:p@host/db', 'postgresql+psycopg://u:p@host/db'),
    # Only the scheme changes: a password containing 'postgres://' stays untouched.
    ('postgres://u:postgres://x@host/db', 'postgresql+psycopg2://u:postgres://x@host/db'),
    (None, None),
    ('', ''),
])
def test_normalize_database_url(given, expected):
    assert normalize_database_url(given) == expected


def test_the_configured_driver_is_installed():
    """Guards against a dependency bump that changes which driver a URL resolves to."""
    from sqlalchemy import create_engine
    engine = create_engine(normalize_database_url('postgresql://u:p@localhost/db'))
    assert engine.dialect.driver == 'psycopg2'
