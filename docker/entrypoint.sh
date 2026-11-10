#!/bin/sh
# Container entrypoint: apply pending migrations, then hand over to CMD (gunicorn).
#
# - 'flask db upgrade' is idempotent: with no pending revisions it does nothing,
#   so it is safe on every start and on every Render deploy.
# - Retries cover a database that accepts TCP but is still starting.
# - Seed data is NEVER loaded here: production must not get demo users by accident
#   (see scripts/dev.sh seed and docs/DEPLOY.md).
# - RUN_MIGRATIONS=0 skips the step (e.g. a one-off command against a read-only DB).
set -eu

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  attempt=1
  max="${MIGRATION_RETRIES:-10}"
  until flask --app app db upgrade; do
    if [ "$attempt" -ge "$max" ]; then
      echo "entrypoint: migrations failed after $attempt attempts" >&2
      exit 1
    fi
    echo "entrypoint: database not ready (attempt $attempt/$max), retrying in 3s" >&2
    attempt=$((attempt + 1))
    sleep 3
  done
fi

exec "$@"
