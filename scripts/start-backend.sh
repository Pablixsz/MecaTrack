#!/usr/bin/env bash
# Arranca el backend de MecaTrack en http://127.0.0.1:5000
#
# Uso (desde cualquier carpeta):
#   ./scripts/start-backend.sh            # arranca el servidor
#   ./scripts/start-backend.sh --migrate  # aplica migraciones pendientes y arranca
#
# - Crea backend/venv e instala dependencias si no existen.
# - Exige backend/.env (se copia de .env.example la primera vez).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND="$ROOT/backend"
cd "$BACKEND"

if [ ! -d venv ]; then
  echo "==> Creando entorno virtual en backend/venv"
  python3 -m venv venv
  venv/bin/pip install --quiet --upgrade pip
  venv/bin/pip install --quiet -r requirements.txt
elif ! venv/bin/python -c "import flask, flask_migrate, flask_jwt_extended, flask_cors, psycopg2" 2>/dev/null; then
  echo "==> Instalando dependencias faltantes"
  venv/bin/pip install --quiet -r requirements.txt
fi

if [ ! -f .env ]; then
  cp .env.example .env
  echo "!! Se creo backend/.env a partir de .env.example."
  echo "   Edita DATABASE_URL con tu usuario/contrasena de PostgreSQL y vuelve a ejecutar."
  exit 1
fi

if command -v pg_isready >/dev/null 2>&1 && ! pg_isready -h 127.0.0.1 -p 5432 -q; then
  echo "!! PostgreSQL no responde en 127.0.0.1:5432. Inicialo (ej: sudo systemctl start postgresql)."
  exit 1
fi

if [ "${1:-}" = "--migrate" ]; then
  echo "==> Aplicando migraciones (flask db upgrade)"
  venv/bin/flask --app app db upgrade
fi

echo "==> Backend en http://127.0.0.1:5000  (Ctrl+C para detener)"
exec venv/bin/python app.py
