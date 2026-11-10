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

## Phase 3 — docker compose

**AI generated:** `docker-compose.yml` (postgres:16-alpine with named volume and `pg_isready`; app with
`depends_on: service_healthy`, `/health` check, `restart: unless-stopped`), root `.env.example`, `scripts/dev.sh`
(`up down reset seed logs test e2e ps`; `up` creates `.env` with random secrets, mode 600).

**Why:** required variables use `${VAR:?message}` so compose refuses to start without secrets instead of starting
with empty ones; the database is published only on `127.0.0.1:5433` (no clash with a local PostgreSQL, not exposed
to the network).

**Results (real):** from zero (`down -v`) both services healthy; entrypoint applied the 4 migrations; seed loaded
manually; login 200; 257 tests passed against the compose database; E2E passed (appointment #3); `db` stopped →
`/health` 503, started → 200 without restarting the app (`docs/evidence/p3-*`).

**What failed / was corrected:**
- First E2E run against compose timed out on the admin login. Cause: HTTP 429 — the login rate limit (5/min) counted
  the `curl` login done right before plus the script's 5 logins. The app behaved correctly; the script now honours
  `Retry-After` and retries once (the second run shows the wait).

## Phase 4 — CI/CD pipeline (4 stages)

**AI generated:** `.github/workflows/ci-cd.yml` (test → build → push → deploy, chained with `needs`; PRs run only
test + build); `backend/ruff.toml`; `/health` now reports `version` (commit SHA baked by `--build-arg APP_VERSION`).
Existing workflows (`mecatrack-tests.yml` with mutation testing + SonarCloud, `codeql.yml`) left untouched.

**Design decisions:**
- Actions pinned by commit SHA (as the repo already did). The AI first resolved tags with `git ls-remote --refs`,
  noticed that for *annotated* tags that returns the tag object, not the commit, and re-checked the peeled refs:
  all four Docker actions use lightweight tags, so the SHAs were right.
- The deploy hook is called with `imgURL=<image>:sha-<short>` so Render deploys this commit's image, not whatever
  `:latest` is; the job then waits until the public `/health` reports *this* commit, so an old instance answering
  200 cannot fake a successful deploy.
- Smoke test uses a `postgres://` URL on purpose to exercise the normalisation PaaS providers need.
- Coverage gate 90 % (current 97.42 %).
- Lint scope: ruff ≥ 0.17 enables many rules by default (135 findings, mostly style in legacy code). Chosen set:
  E, F, W, B with E501 ignored. Real findings fixed: 7 missing final newlines, 3 `raise … from` (B904), 1
  `zip(strict=True)` (B905).
- bandit: 13 findings, 0 high. The 6 medium B608 ("SQL injection") were reviewed: the DuckDB queries are constants
  built at import time and view names come from a fixed map, so they are false positives → `# nosec B608` with the
  reason. 1 B311 (retry jitter) suppressed likewise. 6 low B105 ("hardcoded password": `'Bearer'`, test config,
  OpenAPI examples) are reported but do not fail the gate (`--severity-level medium`). pip-audit: no known vulnerabilities.

**Verified locally (real):** actionlint 1.7.12 + shellcheck → 0 errors in the 3 workflows; the `test` job's commands
extracted from the YAML and executed → exit 0; the `build` job's smoke-test script extracted from the YAML and
executed against a freshly built image → healthy, version = commit, user `app`.

**NOT verified (needs GitHub/Docker Hub/Render):** the GHA layer cache, Docker Hub login and push, the Render deploy
hook with `imgURL` and the public URL check. These run for the first time on the first push to `main`.

**What failed / was corrected:**
- bandit read the words written after `# nosec B608 - …` as test IDs and warned; the justification now goes before
  the marker. bandit still prints "nosec encountered but no failed test" for lines inside multi-line strings — a
  known bandit quirk, harmless.

## Phase 5 — Render deployment (configuration only)

**AI generated:** `render.yaml` (Blueprint: image-backed web service + free PostgreSQL 16, generated secrets,
`PROXY_FIX_HOPS=1`, `/health` check) and `docs/DEPLOY.md` (ordered steps, secrets, manual seed, limitations,
troubleshooting).

**Verification:** instead of trusting memory, the AI read Render's current docs (render.com/docs/free and
/docs/deploy-hooks, 2026-11-09). Confirmed: spin-down after 15 min idle (~1 min to wake), free Postgres expires
after 30 days (+14 days grace), 1 GB, one per workspace, no shell/disk on free. Found a detail that changed the
design: `imgURL` must match the service image URL in everything but the tag → the guide insists on the
`docker.io/` prefix. `render.yaml` validated against Render's official JSON Schema (render.com/schema/render.yaml.json): valid.

**Ordering decision:** the first image is pushed by hand before creating the service (Render needs it to exist)
and the hook/URL secrets are set before merging to `main`, so the first pipeline run on `main` can be green.

**NOT verified:** that the free instance type accepts image-backed services (the free-plan page does not say it
explicitly), the hook call and the public URL — they need the team's Render account.

## Phase 6 — Demo: JWT and quality metrics

**Human decision (Phase 0):** do not touch authentication — JWT + RBAC already existed (Flask-JWT-Extended).

**AI generated:** `scripts/demo_jwt.sh` (9 live cases with curl: valid 200, wrong role 403, no token 401, tampered
role claim 401, garbage token 401, expired token 401 `token_expired`, admin 200, logout then reuse 401
`token_revoked`) and `scripts/quality_report.sh` (tests, line/branch coverage, ruff, bandit, pip-audit →
console summary + `docs/quality-report.md`).

**Design note:** a token signed with a wrong key that is also expired is rejected for its *signature*, which would
not demonstrate expiry. The script signs the expired token with the real key (stdlib HMAC-SHA256, no dependencies),
read from `JWT_SECRET_KEY` or the local `.env`; against a server whose key it does not have, the case is reported
as SKIP, never faked.

**Results (real):** demo 9/9 passed against the compose stack; quality report: 257/257 tests, 97.42 % line,
90.59 % branch coverage, 0 ruff findings, bandit 0 high/medium (6 low false positives), 0 vulnerable dependencies
in 54 packages (`docs/evidence/p6-*`).

**What failed / was corrected:**
- First run of `quality_report.sh` crashed: the AI read `summary.missing_lines` from coverage's JSON, which is a
  count; the list is `files[f].missing_lines`.
- The generated report said the B105 findings were "reviewed by the team" — not true yet (the AI reviewed them).
  Reworded to point to this log. **Team: please confirm that review.**
- shellcheck: 4 × SC2164 (`cd` without `|| exit`) fixed; 3 × SC2016 are intentional (variables expand inside the
  database container) and annotated.

## Phase 7 — README and documentation

**AI generated:** a new English `README.md` (1335 words by `wc -w`; 1054 excluding code blocks and badges) with
features by role, stack, Mermaid architecture diagram, quick start, configuration, security, CI/CD, deployment,
tests, structure, AI usage and authors; `docs/architecture.png` (the same diagram rendered with mermaid-cli 11.4.2,
which also validated the Mermaid syntax).

**Kept from the previous (Spanish) README:** roles, scheduling engine, security section, OWASP link. Detailed local
setup without Docker is no longer in the README; `scripts/start-backend.sh` still works.

**Corrections made on the way:** the old README said "individual project" and "seed.sql hashes cannot log in"; both
were outdated (team of three; the seed was fixed in Phase 1).

**Placeholders left for the team:** `<DOCKERHUB_USERNAME>` (4), `<PUBLIC_URL>`, `<AUTHOR_2>`, `<AUTHOR_3>`,
`<LICENSE>`. There is no LICENSE file: the AI did not pick a license because that is the authors' decision.

## Extra — Demo slides

**AI generated:** `docs/slides/build_slides.js` (pptxgenjs 4.0.1, pinned in `docs/slides/package.json`) and
`docs/slides/MecaTrack_Lab8_Demo.pptx`: 3 English slides (architecture, pipeline + image size chart, quality metrics +
JWT results) with speaker notes. All numbers are copied from generated reports, not invented.

**QA:** file validated (OOXML schema and package checks) and rendered with LibreOffice. The first render had real
defects that were fixed: inconsistent title alignment, words split across lines ("pip-audit", "90 %"), a label touching
its card edge, and the bar chart showing the "before" bar at the bottom. The build also strips ZIP folder entries
that break opening the deck from cloud storage.

**For the team:** slide 2 has a dashed frame where the screenshot of the green pipeline goes (after the first merge).

## After the push — a vulnerability the AI introduced

After pushing `mecatrack-final`, Dependabot flagged `docs/slides`: pptxgenjs 4.0.1 (added by the AI for the slides)
depends on `image-size@1.2.1`, with two **high** advisories (GHSA-5p2g-fcmc-qvqq, GHSA-w3rx-r6r6-pgpr: infinite loops
→ DoS while parsing JXL/HEIF/ICNS images). Real risk was low (local build, own images only), but the AI should have
run `npm audit` before committing; pip-audit only covered the Python side. Fix: `overrides` pins `image-size` to
2.1.0 (patched). The AI checked that pptxgenjs never imports `image-size` at runtime (it calls `require('sizeof')`),
rebuilt the deck and confirmed identical slide content and a valid file. `npm audit`: 0 vulnerabilities.

## After the Dependabot merges — SQLAlchemy 2.1 switched the PostgreSQL driver

The team merged 10 Dependabot PRs into `mecatrack-final`, including SQLAlchemy 2.0.52 → 2.1.8 and google-genai
2.34 → 3.0. The remote "pruebas de integracion" run went red. Locally: 108 of 257 tests errored and `create_app()`
crashed with `ModuleNotFoundError: No module named 'psycopg'`. Cause: SQLAlchemy 2.1 maps a bare `postgresql://` to
psycopg (v3) instead of psycopg2; the project ships `psycopg2-binary`.

**Fix (smallest change):** `normalize_database_url` now pins `postgresql+psycopg2://` for bare `postgres://` and
`postgresql://` URLs (an explicit driver is respected). Added a guard test that builds an engine and asserts the
driver is psycopg2, so a future bump fails loudly in unit tests. The Lab 7 seed script uses the same helper.
google-genai 3.0: the gateway's calls (`Client`, `HttpOptions`, `models.generate_content`, `GenerateContentConfig`,
`errors.APIError`) were checked against the installed 3.0.0 — the AI tests mock the LLM, so this was verified apart.

**Results (real):** 259/259 tests, 97.42 % coverage, ruff/bandit/pip-audit clean (57 packages), OpenAPI unchanged,
image rebuilt and the CI smoke test passed.

**AI mistake caught on the way:** the first smoke-test rerun reused a script generated earlier with an old commit SHA
hard-coded, and the reported `exit=0` was `tail`'s, not the script's. The AI noticed the missing last line, regenerated
the script with the current SHA and captured the real exit code before reporting success.

**Lesson for the team:** Dependabot PRs were merged without waiting for the integration checks; a required status
check on the branch (Settings → Branches) would have blocked the breaking one.
