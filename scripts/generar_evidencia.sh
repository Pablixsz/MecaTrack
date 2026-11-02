#!/usr/bin/env bash
# Guia 6: regenera TODA la evidencia en un solo paso.
#
#   ./scripts/generar_evidencia.sh            todo: pruebas, capturas 01-17 e informe Word
#   ./scripts/generar_evidencia.sh --sin-web  sin las capturas de GitHub (CI y ADR)
#
# Pasos:
#   1. Dependencias (backend + evidencia) y Chromium de Playwright
#   2. Descarga real de los datos abiertos (datos.gov.co y DANE) -> backend/var/market_data
#   3. Capturas de terminal (pytest, codigo, APIs reales, demo de resiliencia, DuckDB)
#   4. Backend + frontend reales -> capturas de la UI y de Swagger
#   5. DEMOSTRACION CONTROLADA: backend con datos.gov.co apuntando a un host .invalid -> breaker OPEN en la UI
#   6. Capturas de GitHub (run de Actions y ADR renderizado) -> requiere haber hecho push
#   7. Informe Word (Node + docx)
#
# Requisitos: PostgreSQL corriendo, backend/.env, Node 18+, red. Puertos 5000 y 5500 libres.
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT=$(pwd)
PY=backend/venv/bin/python
WEB=true
[ "${1:-}" = "--sin-web" ] && WEB=false
step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "1. Dependencias"
[ -d backend/venv ] || python3 -m venv backend/venv
backend/venv/bin/pip install -q -r backend/requirements-dev.txt -r scripts/requirements-evidence.txt
$PY -m playwright install chromium > /dev/null
if command -v pg_isready > /dev/null && ! pg_isready -h 127.0.0.1 -p 5432 -q; then
  echo "!! PostgreSQL no responde en 127.0.0.1:5432" >&2; exit 1
fi
for port in 5000 5500; do
  if (exec 3<>"/dev/tcp/127.0.0.1/$port") 2>/dev/null; then
    echo "!! El puerto $port ya esta en uso. Deten ese servidor y vuelve a intentar." >&2; exit 1
  fi
done
mkdir -p docs/evidencia/salidas
rm -f docs/evidencia/*.png docs/evidencia/salidas/*

step "2. Descarga real de datos abiertos"
(cd backend && venv/bin/python -c "
from app import create_app
app = create_app()
for r in app.extensions['mecatrack'].market_data.refresh():
    print(f'  {r.source:16} ok={r.ok} filas={r.rows} {r.elapsed_ms} ms {r.error or \"\"}')
    assert r.ok, r.error
")

step "3. Capturas de terminal (01-12)"
$PY scripts/evidencia/capturar.py terminal

LOGS=$(mktemp -d)
BACKEND_PID=""; FRONTEND_PID=""
stop_servers() { kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; wait $BACKEND_PID $FRONTEND_PID 2>/dev/null || true; }
trap stop_servers EXIT
start_backend() {  # $@: variables de entorno extra
  (cd backend && exec env "$@" venv/bin/flask --app app run --host 127.0.0.1 --port 5000) > "$LOGS/backend.log" 2>&1 &
  BACKEND_PID=$!
  for _ in $(seq 60); do curl -s -o /dev/null http://127.0.0.1:5000/openapi.json && return 0; sleep 0.5; done
  echo "!! El backend no arranco; ver $LOGS/backend.log" >&2; exit 1
}
(cd frontend && exec python3 -m http.server 5500 --bind 127.0.0.1) > "$LOGS/frontend.log" 2>&1 &
FRONTEND_PID=$!

step "4. UI real: panel Mercado y Swagger (13, 17)"
start_backend FLASK_DEBUG=0
$PY scripts/evidencia/capturar.py ui
kill $BACKEND_PID; wait $BACKEND_PID 2>/dev/null || true

step "5. DEMOSTRACION CONTROLADA: datos.gov.co -> host .invalid (14)"
start_backend MARKET_SOCRATA_BASE_URL=https://datos-gov-co.invalid/resource MARKET_MAX_RETRIES=1
$PY scripts/evidencia/capturar.py ui-breaker
stop_servers; trap - EXIT

if $WEB; then
  step "6. GitHub: CI en verde y ADR (15, 16)"
  $PY scripts/evidencia/capturar.py web
else
  step "6. Capturas de GitHub OMITIDAS (--sin-web)"
fi

step "7. Informe Word"
if [ -f informe/build_informe_guia6.js ]; then
  [ -d informe/node_modules ] || (cd informe && npm install --ignore-scripts --no-audit --no-fund --silent)
  (cd informe && node build_informe_guia6.js)
else
  echo "  (todavia no existe informe/build_informe_guia6.js)"
fi

step "Listo: $(ls docs/evidencia/*.png | wc -l) capturas en docs/evidencia/ y salidas en docs/evidencia/salidas/"
