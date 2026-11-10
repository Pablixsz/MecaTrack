# AI Usage Log — Lab 8 (Cloud-Native Deployment)

Tool: Claude Code (Claude Opus 5.5) working in the repository, supervised by the team.
Each entry states what the AI generated, what a human reviewed or decided, and what went
wrong. Commands and results are real; nothing here is simulated.

---

## Phase 0 — Audit (read only)

**AI did:** read the repository and ran the existing test suite before changing anything.

**Findings that contradicted the task brief** (the brief was written from memory and was outdated):
- The backend is hexagonal (`api/ application/ domain/ infrastructure/`), not `db/ models/ routes/ middlewares/`.
- Authentication is already JWT (Flask-JWT-Extended, Bearer header, RBAC, logout blocklist); there is no Flask-Login.
- There were already 241 tests. Locally 98 "failed": all were `database "taller_mecanico_test" does not exist` (environment, not code).
- `database/seed.sql` stored the literal `hashed_password_123` as password hash: on a fresh database nobody could log in.
- `frontend/js/api.js` hard-coded `http://127.0.0.1:5000`, and the API sent `Content-Security-Policy: default-src 'none'` on every response: both would break the frontend once served from the same public URL.
- Behind a PaaS proxy, `request.remote_addr` is the proxy: the login rate limit would be shared by every user and HSTS never sent.

**Human decisions:** keep the existing JWT (no auth rewrite), use the team remote `Pablixsz/MecaTrack`, fix `seed.sql` in place.

## Phase 1 — Production-ready base

**AI generated:** `GET /health` (port `HealthProbe` in `domain`, adapter in `infrastructure`, route in `api`, wired in
`bootstrap.py` so the architecture test still passes); `postgres://` → `postgresql://` normalisation; `PROXY_FIX_HOPS`
(Werkzeug `ProxyFix`); frontend served by Flask from explicit prefixes with its own CSP; same-origin `api.js`;
`docker/entrypoint.sh` (idempotent `flask db upgrade` with retries, never seeds); `gunicorn.conf.py`
(1 worker × 4 threads); real scrypt hashes in `seed.sql` plus an admin user; 16 new tests; `scripts/e2e_flow.py`
(Playwright, real UI).

**Why these choices:**
- One worker with threads: the rate limiter and the JWT blocklist live in process memory; several workers would
  each have their own copy (a revoked token would still be valid on another worker).
- Explicit frontend prefixes instead of a catch-all route: a catch-all would answer unknown API paths with HTML.
- The test password hash in `seed.sql` is not a secret: it is the public demo password `test1234`.

**Results (real):** baseline 241 passed / 97 % coverage → 257 passed / 97 % coverage. `docs/openapi.json` unchanged.
E2E through gunicorn: appointment booked, deposit paid, tracked, completed; no CSP or JS errors
(`docs/evidence/p1-*`).

**What failed / was corrected:**
- One of the AI's own new tests asserted the page title contained "MecaTrack"; the real title is "Taller Mecánico". Test fixed (the app was right).
- `pkill -f gunicorn` matched the AI's own shell command line and killed it (exit 144) twice; fixed with a `bin/[g]unicorn` pattern.
- SonarLint flagged `random` in the E2E script (S2245) and then a comment containing the word NOSONAR (S7632); reworded.
- Ruff 0.17 enables many more rules by default (135 findings on legacy code even with `--isolated`); an explicit rule set is deferred to Phase 4.

## Phase 2 — Optimized Dockerfile

**AI generated:** multi-stage `Dockerfile` (builder venv → `python:3.12-slim` runtime, uid 10001, read-only code,
`HEALTHCHECK` with the Python stdlib because slim has no curl), `.dockerignore`, `docs/docker/Dockerfile.naive`
and `docs/docker/size-comparison.md`. `scripts/evidence/evidence_index.py` gained an `EVIDENCE_DIR` override so the
Lab 7 terminal-capture tool writes Lab 8 evidence (default behaviour unchanged).

**Why:** a copied virtualenv instead of a wheel directory keeps pip and wheels out of the runtime layer; the code is
owned by root so a compromised process cannot rewrite it.

**Results (real):** 2.27 GB → 436 MB on disk (−80.8 %), 658 MB → 105 MB compressed (−84 %). `docker exec … whoami`
→ `app`; container `healthy`; full E2E flow passed against the container (appointment #12).

**What failed / was corrected:**
- Gunicorn 26 logged `Control server error: Permission denied: '/app/.gunicorn'` — new in that version, it opens a
  control socket in `$HOME`, which the non-root user cannot write. Fixed with `control_socket_disable = True`.
  It was caught only because the AI read the container logs after the health check had already passed.
