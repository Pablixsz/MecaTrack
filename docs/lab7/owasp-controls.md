# OWASP API Security Top 10 2023 - implemented controls

9 of the 10 risks have a control and an automated test. File and line references are generated from the
current code by `scripts/evidence/build_owasp_table.py`.

| Risk | Control implemented | File/line | Test/evidence |
|---|---|---|---|
| API1:2023 Broken Object Level Authorization | Every vehicle, appointment and payment lookup checks that the caller owns or participates in the object. | `backend/domain/scheduling/rules.py:24`<br>`backend/application/catalog/services.py:301`<br>`backend/application/payments/services.py:38` | `backend/tests/integration/test_owasp_controls.py`: `test_api1_*` |
| API2:2023 Broken Authentication | Short-lived signed JWT with revocation on logout, rate-limited login, one generic message for wrong email or password, equal hashing cost for unknown accounts, and a minimum password length. | `backend/config.py:25`<br>`backend/api/jwt_routes.py:17`<br>`backend/application/identity/services.py:43`<br>`backend/api/auth.py:25` | `backend/tests/integration/test_owasp_controls.py`: `test_api2_*`; `backend/tests/integration/test_jwt_auth.py`; `backend/tests/unit/test_auth_service.py`; Figures 06b and 07e |
| API3:2023 Broken Object Property Level Authorization | Responses are built from explicit field lists, so `password_hash` is never returned. Registration fixes the role to `client`, and updates only accept whitelisted fields. | `backend/api/legacy/auth_routes.py:20`<br>`backend/api/legacy/vehicle_routes.py:53`<br>`backend/application/catalog/services.py:289` | `backend/tests/integration/test_owasp_controls.py`: `test_api3_*` |
| API4:2023 Unrestricted Resource Consumption | Global and login rate limits, a 1 MB request body limit and capped pagination. The AI endpoint also has a per-user hourly quota. Limitation: pagination cuts the response, not the database query. | `backend/config.py:28`<br>`backend/config.py:29`<br>`backend/api/legacy/__init__.py:10`<br>`backend/application/ai_assistant/services.py:37` | `backend/tests/integration/test_owasp_controls.py`: `test_api4_*`; Figure 09c |
| API5:2023 Broken Function Level Authorization | Each route declares its allowed roles with `@role_required`; missing token gives 401 and a wrong role gives 403. Management endpoints only accept `owner` and `admin`. | `backend/api/auth.py:94`<br>`backend/api/legacy/bay_routes.py:17`<br>`backend/api/v1/services.py:25` | `backend/tests/integration/test_jwt_auth.py`: `test_admin_endpoint_accepts_only_admin`, `test_management_endpoints_reject_client_and_mechanic`; Figures 07b and 07f |
| API6:2023 Unrestricted Access to Sensitive Business Flows | A client can hold at most 5 active appointments, and an appointment can only be confirmed after its deposit is paid. | `backend/domain/scheduling/rules.py:8`<br>`backend/application/scheduling/services.py:49`<br>`backend/application/scheduling/services.py:104` | `backend/tests/integration/test_owasp_controls.py`: `test_api6_*`; `backend/tests/unit/test_appointment_service.py` |
| API8:2023 Security Misconfiguration | Debug is off by default, CORS is an explicit allowlist without credentials, secrets come from the environment, security headers are set on every response and unexpected errors never expose a stack trace. | `backend/app.py:43`<br>`backend/app.py:24`<br>`backend/app.py:21`<br>`backend/api/__init__.py:71`<br>`backend/api/__init__.py:35` | `backend/tests/integration/test_owasp_controls.py`: `test_api8_*`; `backend/tests/integration/test_jwt_auth.py`: `test_app_refuses_to_start_without_a_signing_key`; Figure 09d |
| API9:2023 Improper Inventory Management | All `/api/` routes must appear in the versioned OpenAPI document, and CI fails if `docs/openapi.json` is out of date. | `backend/api/openapi.py:48`<br>`.github/workflows/mecatrack-tests.yml:84` | `backend/tests/integration/test_owasp_controls.py`: `test_api9_every_api_route_is_documented` |
| API10:2023 Unsafe Consumption of APIs | External API calls use timeouts, retries and a circuit breaker. LLM answers are parsed strictly, and service ids that were not in the supplied context are discarded. | `backend/infrastructure/resilience/http_client.py:26`<br>`backend/infrastructure/resilience/circuit_breaker.py:46`<br>`backend/domain/ai_assistant/answer.py:12` | `backend/tests/unit/test_circuit_breaker.py`; `backend/tests/unit/test_resilient_http_client.py`; `backend/tests/integration/test_api_v1_ai.py` |

## Not covered

- **API7:2023 Server Side Request Forgery:** no endpoint accepts a URL from the user. Outbound hosts are fixed in configuration, so there is no user-controlled request to protect.

## Known limitations

- The token blocklist and the rate-limit counters live in the memory of one server process. They reset on restart and are not shared between processes; a production deployment needs a shared store such as Redis.
- The login rate limit is per IP address, so it does not stop a distributed attack on a single account.
- The JWT is kept in `sessionStorage`, which any script on the page can read. The mitigation is escaping rendered data and using short-lived tokens.
