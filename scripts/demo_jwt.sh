#!/usr/bin/env bash
# MecaTrack - live JWT / RBAC demo with curl.
#
#   ./scripts/demo_jwt.sh                                  # local stack (http://localhost:8000)
#   ./scripts/demo_jwt.sh https://mecatrack-xxxx.onrender.com
#
# Cases: valid token (200), role claim is signed (tampered -> 401), wrong role (403),
# no token (401), forged signature (401), expired token (401), logout revokes the token (401).
#
# The expired-token case signs a token with the REAL key, so the server rejects it for being
# expired and not for its signature. It needs JWT_SECRET_KEY in the environment (or in ./.env
# for the local stack); without it that case is skipped, never faked.
#
# Uses the seed users (password test1234). Needs curl, jq and python3 (standard library only).
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

BASE="${1:-${BASE_URL:-http://localhost:8000}}"; BASE="${BASE%/}"
PASSWORD='test1234'
CLIENT='laura.cliente@gmail.com'
ADMIN='admin@tallermecanico.com'

if [ -t 1 ]; then G=$'\e[32m'; R=$'\e[31m'; Y=$'\e[33m'; B=$'\e[1m'; N=$'\e[0m'; else G=; R=; Y=; B=; N=; fi
pass=0; fail=0; skip=0

title() { printf '\n%s== %s%s\n' "$B" "$1" "$N"; }

# check <description> <expected status> <curl args...> : prints status + JSON body, counts the result.
check() {
  local desc="$1" expected="$2"; shift 2
  local out status body
  out="$(curl -sS -w '\n%{http_code}' "$@")"
  status="${out##*$'\n'}"; body="${out%$'\n'*}"
  printf '   %s\n' "$(echo "$body" | jq -c . 2>/dev/null || echo "$body")"
  if [ "$status" = "$expected" ]; then
    printf '   %sPASS%s %s -> HTTP %s\n' "$G" "$N" "$desc" "$status"; pass=$((pass + 1))
  else
    printf '   %sFAIL%s %s -> HTTP %s (expected %s)\n' "$R" "$N" "$desc" "$status" "$expected"; fail=$((fail + 1))
  fi
  LAST_BODY="$body"
}

login() {
  curl -sS -X POST "$BASE/api/auth/login" -H 'Content-Type: application/json' \
       -d "{\"email\":\"$1\",\"password\":\"$PASSWORD\"}"
}

claims() {  # decoded payload of a JWT (base64url, no signature check: anyone can read it)
  python3 -c 'import base64, json, sys; p = sys.argv[1].split(".")[1]; p += "=" * (-len(p) % 4); print(json.dumps(json.loads(base64.urlsafe_b64decode(p)), indent=None))' "$1"
}

auth() { printf 'Authorization: Bearer %s' "$1"; }

echo "${B}MecaTrack JWT demo${N} against $BASE"
curl -fsS "$BASE/health" >/dev/null || { echo "${R}$BASE/health is not answering${N}"; exit 1; }

title "1. Login as client -> access token"
resp="$(login "$CLIENT")"
CLIENT_TOKEN="$(echo "$resp" | jq -r '.access_token // empty')"
if [ -z "$CLIENT_TOKEN" ]; then echo "${R}login failed:${N} $resp"; exit 1; fi
echo "$resp" | jq -c '{token_type, expires_in, role, access_token: (.access_token[0:30] + "...")}'
echo "   payload (readable by anyone, protected by the signature):"
echo "   $(claims "$CLIENT_TOKEN")"

title "2. Valid token on an endpoint for clients"
check "client token on /api/rbac/user" 200 "$BASE/api/rbac/user" -H "$(auth "$CLIENT_TOKEN")"

title "3. Role without permission: client token on the admin endpoint"
check "client token on /api/rbac/admin" 403 "$BASE/api/rbac/admin" -H "$(auth "$CLIENT_TOKEN")"

title "4. No token"
check "no Authorization header" 401 "$BASE/api/rbac/admin"

title "5. Tampered token: change the role claim to admin, keep the signature"
TAMPERED="$(python3 - "$CLIENT_TOKEN" <<'EOF'
import base64, json, sys
header, payload, signature = sys.argv[1].split('.')
data = json.loads(base64.urlsafe_b64decode(payload + '=' * (-len(payload) % 4)))
data['role'] = 'admin'
forged = base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode()).rstrip(b'=').decode()
print(f'{header}.{forged}.{signature}')
EOF
)"
echo "   forged payload: $(claims "$TAMPERED")"
check "tampered token on /api/rbac/admin" 401 "$BASE/api/rbac/admin" -H "$(auth "$TAMPERED")"

title "6. Garbage / wrongly signed token"
check "invalid token" 401 "$BASE/api/rbac/user" -H "$(auth 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIzIn0.not-a-signature')"

title "7. Expired token (signed with the real key, exp in the past)"
KEY="${JWT_SECRET_KEY:-}"
if [ -z "$KEY" ] && [ -f .env ] && [[ "$BASE" =~ ^http://(localhost|127\.0\.0\.1) ]]; then
  KEY="$(grep -E '^JWT_SECRET_KEY=' .env | tail -1 | cut -d= -f2-)"
fi
if [ -n "$KEY" ]; then
  USER_ID="$(claims "$CLIENT_TOKEN" | jq -r .sub)"
  EXPIRED="$(JWT_KEY="$KEY" python3 - "$USER_ID" <<'EOF'
import base64, hashlib, hmac, json, os, sys, time, uuid
b64 = lambda raw: base64.urlsafe_b64encode(raw).rstrip(b'=').decode()
now = int(time.time())
header = b64(json.dumps({'alg': 'HS256', 'typ': 'JWT'}, separators=(',', ':')).encode())
payload = b64(json.dumps({'sub': sys.argv[1], 'role': 'client', 'type': 'access', 'fresh': False,
                          'jti': str(uuid.uuid4()), 'iat': now - 1800, 'nbf': now - 1800,
                          'exp': now - 900}, separators=(',', ':')).encode())
signature = b64(hmac.new(os.environ['JWT_KEY'].encode(), f'{header}.{payload}'.encode(), hashlib.sha256).digest())
print(f'{header}.{payload}.{signature}')
EOF
)"
  echo "   exp = $(claims "$EXPIRED" | jq -r '.exp | todate') (15 minutes ago)"
  check "expired token" 401 "$BASE/api/rbac/user" -H "$(auth "$EXPIRED")"
  echo "$LAST_BODY" | jq -e '.code == "token_expired"' >/dev/null && echo "   code = token_expired (not a signature error)"
else
  printf '   %sSKIP%s set JWT_SECRET_KEY to sign an expired token for %s\n' "$Y" "$N" "$BASE"; skip=$((skip + 1))
fi

title "8. Admin token on the admin endpoint"
ADMIN_TOKEN="$(login "$ADMIN" | jq -r '.access_token // empty')"
check "admin token on /api/rbac/admin" 200 "$BASE/api/rbac/admin" -H "$(auth "$ADMIN_TOKEN")"

title "9. Logout revokes the token (jti blocklist)"
check "logout" 200 -X POST "$BASE/auth/logout" -H "$(auth "$ADMIN_TOKEN")"
check "same token after logout" 401 "$BASE/api/rbac/admin" -H "$(auth "$ADMIN_TOKEN")"

printf '\n%sResult:%s %s%d passed%s, %s%d failed%s, %d skipped\n' "$B" "$N" "$G" "$pass" "$N" "$R" "$fail" "$N" "$skip"
[ "$fail" -eq 0 ]
