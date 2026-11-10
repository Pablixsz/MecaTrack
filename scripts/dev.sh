#!/usr/bin/env bash
# MecaTrack - local stack helper (docker compose).
#
#   ./scripts/dev.sh up      build and start db + app, wait until healthy
#   ./scripts/dev.sh down    stop the stack (keeps the database volume)
#   ./scripts/dev.sh reset   DESTROY the local database volume and start from zero
#   ./scripts/dev.sh seed    load database/seed.sql (demo users, password test1234)
#   ./scripts/dev.sh logs    follow the logs (extra args go to docker compose logs)
#   ./scripts/dev.sh test    run the pytest suite against the compose database
#   ./scripts/dev.sh e2e     run the browser end-to-end flow against the stack
#   ./scripts/dev.sh ps      show services and health
#
# Only touches this project's compose stack (project name "mecatrack").
set -euo pipefail
cd "$(dirname "$0")/.."

compose() { docker compose "$@"; }

ensure_env() {
  if [ -f .env ]; then return; fi
  echo "==> Creating .env from .env.example with random secrets"
  local gen='import secrets; print(secrets.token_urlsafe(32))'
  sed -e "s|^POSTGRES_PASSWORD=$|POSTGRES_PASSWORD=$(python3 -c "$gen")|" \
      -e "s|^SECRET_KEY=$|SECRET_KEY=$(python3 -c "$gen")|" \
      -e "s|^JWT_SECRET_KEY=$|JWT_SECRET_KEY=$(python3 -c "$gen")|" \
      .env.example > .env
  chmod 600 .env
}

env_value() { grep -E "^$1=" .env | tail -1 | cut -d= -f2-; }

wait_healthy() {
  local port; port="$(env_value APP_PORT)"; port="${port:-8000}"
  echo -n "==> Waiting for http://localhost:${port}/health "
  for _ in $(seq 1 60); do
    if curl -fs "http://localhost:${port}/health" >/dev/null 2>&1; then
      echo "OK"; curl -s "http://localhost:${port}/health"; echo; return 0
    fi
    echo -n "."; sleep 2
  done
  echo " TIMEOUT"; compose ps; compose logs --tail 40 app; return 1
}

seed() {
  echo "==> Loading database/seed.sql"
  # -T: no TTY, so the file can be piped in. ON_ERROR_STOP: fail loudly (e.g. seeding twice).
  # shellcheck disable=SC2016  # $POSTGRES_* must expand inside the db container, not here
  compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -q -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < database/seed.sql
  echo "==> Seed loaded. Users: carlos.owner@ / andres.mecanico@tallermecanico.com, laura.cliente@gmail.com, admin@tallermecanico.com (test1234)"
}

run_tests() {
  local venv=backend/venv/bin/python
  if [ ! -x "$venv" ]; then
    echo "!! backend/venv not found: python3 -m venv backend/venv && backend/venv/bin/pip install -r backend/requirements-dev.txt"; exit 1
  fi
  local user pass port
  user="$(env_value POSTGRES_USER)"; pass="$(env_value POSTGRES_PASSWORD)"; port="$(env_value DB_HOST_PORT)"
  # The suite refuses any database whose name does not end in _test: it never touches the app data.
  # shellcheck disable=SC2016  # expanded inside the db container
  compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -tc "SELECT 1 FROM pg_database WHERE datname='"'"'taller_mecanico_test'"'"'" | grep -q 1 || createdb -U "$POSTGRES_USER" taller_mecanico_test'
  local url="postgresql://${user}:${pass}@127.0.0.1:${port:-5433}/taller_mecanico_test"
  (cd backend && TEST_DATABASE_URL="$url" DATABASE_URL="$url" venv/bin/python -m pytest -q -p no:warnings --cov --cov-report=term "$@")
}

cmd="${1:-help}"; shift || true
case "$cmd" in
  up)    ensure_env; compose up -d --build; wait_healthy ;;
  down)  compose down ;;
  reset) ensure_env; echo "==> Removing the local database volume (project mecatrack)"; compose down -v; compose up -d --build; wait_healthy ;;
  seed)  seed ;;
  logs)  compose logs -f "$@" ;;
  test)  run_tests "$@" ;;
  e2e)   port="$(env_value APP_PORT)"; backend/venv/bin/python scripts/e2e_flow.py --base-url "http://localhost:${port:-8000}" "$@" ;;
  ps)    compose ps ;;
  *)     sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; [ "$cmd" = help ] ;;
esac
