#!/usr/bin/env bash
# Capturas de JWT + RBAC con curl real contra un backend local (ver seed_jwt_demo.py).
# :5000 emite tokens normales; :5001 los emite de 2 segundos para demostrar la expiracion.
set -euo pipefail
cd "$(dirname "$0")/../.."
PY=backend/venv/bin/python
API=http://127.0.0.1:5000
login() { curl -s -X POST "$1/api/auth/login" -H 'Content-Type: application/json' \
  -d "{\"email\":\"$2\",\"password\":\"test1234\"}" | $PY -c 'import sys,json;print(json.load(sys.stdin)["access_token"])'; }
export ADMIN_TOKEN=$(login $API admin@demo.test)
export CLIENT_TOKEN=$(login $API client@demo.test)
export SHORT_TOKEN=$(login http://127.0.0.1:5001 client@demo.test)
sleep 3

shot() { $PY scripts/evidence/term_capture.py --file "$1" --phase 4 --desc "$2" "$3" | head -1; }
W='\n[HTTP %{http_code}]\n'
shot 06a-jwt-login-200.png 'POST /api/auth/login con credenciales validas: 200 y token' \
  "curl -s -w '$W' -X POST $API/api/auth/login -H 'Content-Type: application/json' -d '{\"email\":\"admin@demo.test\",\"password\":\"test1234\"}'"
shot 06b-jwt-login-401.png 'POST /api/auth/login con contrasena incorrecta: 401 generico' \
  "curl -s -w '$W' -X POST $API/api/auth/login -H 'Content-Type: application/json' -d '{\"email\":\"admin@demo.test\",\"password\":\"incorrecta\"}'"
shot 06c-jwt-claims.png 'Claims del token: rol y expiracion corta' \
  "echo \"\$ADMIN_TOKEN\" | cut -d. -f2 | $PY -c \"import sys,base64,json;p=sys.stdin.read().strip();print(json.dumps(json.loads(base64.urlsafe_b64decode(p+'='*(-len(p)%4))),indent=2))\""
shot 07a-jwt-admin-200.png 'Endpoint ADMIN con token de admin: 200' \
  "curl -s -w '$W' $API/api/rbac/admin -H \"Authorization: Bearer \$ADMIN_TOKEN\""
shot 07b-jwt-admin-403.png 'Endpoint ADMIN con token de cliente: 403' \
  "curl -s -w '$W' $API/api/rbac/admin -H \"Authorization: Bearer \$CLIENT_TOKEN\""
shot 07c-jwt-user-200.png 'Endpoint USER con token de cliente: 200' \
  "curl -s -w '$W' $API/api/rbac/user -H \"Authorization: Bearer \$CLIENT_TOKEN\""
shot 07d-jwt-401-no-token.png 'Endpoint protegido sin token: 401' \
  "curl -s -w '$W' $API/api/rbac/user"
shot 07e-jwt-expired.png 'Token vencido (emitido con vida de 2 segundos): 401 token_expired' \
  "curl -s -w '$W' http://127.0.0.1:5001/api/rbac/user -H \"Authorization: Bearer \$SHORT_TOKEN\""
shot 07f-jwt-management-403.png 'Endpoint real de gestion (POST /bays) con token de cliente: 403' \
  "curl -s -w '$W' -X POST $API/bays -H 'Content-Type: application/json' -H \"Authorization: Bearer \$CLIENT_TOKEN\" -d '{\"bay_number\":\"Bahia 9\"}'"
