"""Database probe behind GET /health (used by Docker, docker compose and Render)."""

import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from domain.shared.ports import HealthProbe
from infrastructure.persistence.extensions import db

log = logging.getLogger(__name__)


class SqlAlchemyHealthProbe(HealthProbe):
    def is_healthy(self):
        try:
            db.session.execute(text('SELECT 1'))
            return True
        except SQLAlchemyError:
            # The reason goes to the log, never to the (public) response.
            log.exception('Health check: the database did not answer')
            db.session.rollback()
            return False
