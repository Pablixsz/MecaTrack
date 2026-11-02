#!/usr/bin/env bash
# Regenera TODO lo de la Guia 5 en orden, desde cualquier carpeta.
#
#   ./scripts/run_all.sh              pasos sin costo: dependencias, migraciones,
#                                     catalogo, pruebas, OpenAPI, costos e informe
#   ./scripts/run_all.sh --with-llm   ademas repite el experimento (30 llamadas
#                                     reales al LLM) y las capturas (1 llamada)
#
# Requisitos: PostgreSQL corriendo, backend/.env con DATABASE_URL (y
# GEMINI_API_KEY + GEMINI_MODEL para --with-llm), Node 18+ y Graphviz.
set -euo pipefail
cd "$(dirname "$0")/.."

WITH_LLM=false
[ "${1:-}" = "--with-llm" ] && WITH_LLM=true
PY=backend/venv/bin/python
step() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }

step "1. Dependencias del backend"
[ -d backend/venv ] || python3 -m venv backend/venv
backend/venv/bin/pip install -q -r backend/requirements-dev.txt

step "2. Migraciones y catalogo ampliado (idempotente)"
./scripts/seed_catalog.sh > /dev/null
echo "ok"

step "3. Pruebas de integracion -> evidence/pytest_output.txt"
./scripts/run_tests.sh | tail -1

step "4. Especificacion OpenAPI -> docs/openapi.json (validada)"
$PY scripts/export_openapi.py

if $WITH_LLM; then
  step "5. Experimento de prompting (30 llamadas REALES al LLM)"
  $PY scripts/run_prompt_eval.py --delay 5

  step "6. Capturas con Playwright (1 llamada REAL al LLM)"
  backend/venv/bin/pip install -q -r scripts/requirements-evidence.txt
  $PY -m playwright install chromium > /dev/null
  ./scripts/capture_screenshots.sh
else
  step "5-6. Experimento y capturas OMITIDOS (usa --with-llm para repetirlos)"
fi

step "7. Estimacion de costos -> evidence/cost_estimate_EN.md"
$PY scripts/cost_estimate.py | grep -E '^\| (zero_shot|few_shot|cot)'

step "8. Exportacion de ai_calls -> evidence/ai_calls_export.{json,csv}"
$PY scripts/export_ai_calls.py

step "9. Diagrama e informe Word -> informe/Informe_Guia5_MecaTrack.docx"
dot -Tpng -Gdpi=200 informe/arquitectura.dot -o informe/arquitectura.png
[ -d informe/node_modules ] || (cd informe && npm install --ignore-scripts --no-audit --no-fund --silent)
(cd informe && node build_informe.js)

step "Listo. Revisa los cambios con: git status"
