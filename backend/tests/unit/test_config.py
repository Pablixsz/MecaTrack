"""DATABASE_URL normalisation: PaaS providers hand out postgres://, SQLAlchemy 2.0 needs postgresql://."""

import pytest

from config import normalize_database_url


@pytest.mark.parametrize('given, expected', [
    ('postgres://u:p@host:5432/db', 'postgresql://u:p@host:5432/db'),
    ('postgresql://u:p@host:5432/db', 'postgresql://u:p@host:5432/db'),
    ('postgresql+psycopg2://u:p@host/db', 'postgresql+psycopg2://u:p@host/db'),
    # Only the scheme changes: a password containing 'postgres://' stays untouched.
    ('postgres://u:postgres://x@host/db', 'postgresql://u:postgres://x@host/db'),
    (None, None),
    ('', ''),
])
def test_normalize_database_url(given, expected):
    assert normalize_database_url(given) == expected
