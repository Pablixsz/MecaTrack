"""Genera docs/lab7/owasp-controls.md con archivo:linea calculados del codigo actual."""

import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'docs', 'lab7', 'owasp-controls.md')
TESTS = 'backend/tests/integration/test_owasp_controls.py'
JWT_TESTS = 'backend/tests/integration/test_jwt_auth.py'

# (risk, control, [(file, text to locate)], evidence)
CONTROLS = [
    ('API1:2023 Broken Object Level Authorization',
     'Every vehicle, appointment and payment lookup checks that the caller owns or participates in the object.',
     [('backend/domain/scheduling/rules.py', 'def ensure_participant'),
      ('backend/application/catalog/services.py', 'def _owned'),
      ('backend/application/payments/services.py', 'if actor.is_client and appointment.client_user_id')],
     f'`{TESTS}`: `test_api1_*`'),
    ('API2:2023 Broken Authentication',
     'Short-lived signed JWT with revocation on logout, rate-limited login, one generic message for wrong '
     'email or password, equal hashing cost for unknown accounts, and a minimum password length.',
     [('backend/config.py', 'JWT_ACCESS_TOKEN_EXPIRES ='),
      ('backend/api/jwt_routes.py', '@limiter.limit'),
      ('backend/application/identity/services.py', 'self._hasher.verify(self._get_dummy_hash()'),
      ('backend/api/auth.py', 'class TokenBlocklist')],
     f'`{TESTS}`: `test_api2_*`; `{JWT_TESTS}`; `backend/tests/unit/test_auth_service.py`; Figures 06b and 07e'),
    ('API3:2023 Broken Object Property Level Authorization',
     'Responses are built from explicit field lists, so `password_hash` is never returned. Registration fixes '
     'the role to `client`, and updates only accept whitelisted fields.',
     [('backend/api/legacy/auth_routes.py', "container().auth.register(data, role='client')"),
      ('backend/api/legacy/vehicle_routes.py', 'def _serialize_vehicle'),
      ('backend/application/catalog/services.py', 'apply_changes(vehicle, changes, self.EDITABLE)')],
     f'`{TESTS}`: `test_api3_*`'),
    ('API4:2023 Unrestricted Resource Consumption',
     'Global and login rate limits, a 1 MB request body limit and capped pagination. The AI endpoint also has a '
     'per-user hourly quota. Limitation: pagination cuts the response, not the database query.',
     [('backend/config.py', 'MAX_CONTENT_LENGTH ='),
      ('backend/config.py', 'RATELIMIT_DEFAULT ='),
      ('backend/api/legacy/__init__.py', 'def paginate'),
      ('backend/application/ai_assistant/services.py', 'raise UserQuotaExceeded')],
     f'`{TESTS}`: `test_api4_*`; Figure 09c'),
    ('API5:2023 Broken Function Level Authorization',
     'Each route declares its allowed roles with `@role_required`; missing token gives 401 and a wrong role gives 403. '
     'Management endpoints only accept `owner` and `admin`.',
     [('backend/api/auth.py', 'def role_required'),
      ('backend/api/legacy/bay_routes.py', "@role_required('owner', 'admin')"),
      ('backend/api/v1/services.py', 'WRITE_ROLES =')],
     f'`{JWT_TESTS}`: `test_admin_endpoint_accepts_only_admin`, `test_management_endpoints_reject_client_and_mechanic`; '
     'Figures 07b and 07f'),
    ('API6:2023 Unrestricted Access to Sensitive Business Flows',
     'A client can hold at most 5 active appointments, and an appointment can only be confirmed after its deposit is paid.',
     [('backend/domain/scheduling/rules.py', 'MAX_ACTIVE_APPOINTMENTS ='),
      ('backend/application/scheduling/services.py', 'count_active_by_client(client_id) >='),
      ('backend/application/scheduling/services.py', "if new_status == 'confirmed'")],
     f'`{TESTS}`: `test_api6_*`; `backend/tests/unit/test_appointment_service.py`'),
    ('API8:2023 Security Misconfiguration',
     'Debug is off by default, CORS is an explicit allowlist without credentials, secrets come from the environment, '
     'security headers are set on every response and unexpected errors never expose a stack trace.',
     [('backend/app.py', "debug=os.environ.get('FLASK_DEBUG')"),
      ('backend/app.py', "CORS(app, origins="),
      ('backend/app.py', "raise RuntimeError('JWT_SECRET_KEY"),
      ('backend/api/__init__.py', 'def security_headers'),
      ('backend/api/__init__.py', 'LEGACY_HTTP_ERRORS =')],
     f'`{TESTS}`: `test_api8_*`; `{JWT_TESTS}`: `test_app_refuses_to_start_without_a_signing_key`; Figure 09d'),
    ('API9:2023 Improper Inventory Management',
     'All `/api/` routes must appear in the versioned OpenAPI document, and CI fails if `docs/openapi.json` is out of date.',
     [('backend/api/openapi.py', 'AUTH_PATHS ='),
      ('.github/workflows/mecatrack-tests.yml', 'git diff --exit-code -- ../docs/openapi.json')],
     f'`{TESTS}`: `test_api9_every_api_route_is_documented`'),
    ('API10:2023 Unsafe Consumption of APIs',
     'External API calls use timeouts, retries and a circuit breaker. LLM answers are parsed strictly, and service ids '
     'that were not in the supplied context are discarded.',
     [('backend/infrastructure/resilience/http_client.py', 'class '),
      ('backend/infrastructure/resilience/circuit_breaker.py', 'class CircuitBreaker'),
      ('backend/domain/ai_assistant/answer.py', 'def parse_model_answer')],
     '`backend/tests/unit/test_circuit_breaker.py`; `backend/tests/unit/test_resilient_http_client.py`; '
     '`backend/tests/integration/test_api_v1_ai.py`'),
]


def locate(path, text):
    for number, line in enumerate(open(os.path.join(ROOT, path), encoding='utf-8'), 1):
        if text in line:
            return f'`{path}:{number}`'
    raise SystemExit(f'Not found: {text!r} in {path}')


def main():
    rows = [f"| {risk} | {control} | {'<br>'.join(locate(p, t) for p, t in places)} | {evidence} |"
            for risk, control, places, evidence in CONTROLS]
    body = '\n'.join(rows)
    text = f"""# OWASP API Security Top 10 2023 - implemented controls

{len(CONTROLS)} of the 10 risks have a control and an automated test. File and line references are generated from the
current code by `scripts/evidence/build_owasp_table.py`.

| Risk | Control implemented | File/line | Test/evidence |
|---|---|---|---|
{body}

## Not covered

- **API7:2023 Server Side Request Forgery:** no endpoint accepts a URL from the user. Outbound hosts are fixed in configuration, so there is no user-controlled request to protect.

## Known limitations

- The token blocklist and the rate-limit counters live in the memory of one server process. They reset on restart and are not shared between processes; a production deployment needs a shared store such as Redis.
- The login rate limit is per IP address, so it does not stop a distributed attack on a single account.
- The JWT is kept in `sessionStorage`, which any script on the page can read. The mitigation is escaping rendered data and using short-lived tokens.
"""
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f'{len(CONTROLS)} controls -> {os.path.relpath(OUT, ROOT)}')


if __name__ == '__main__':
    main()
