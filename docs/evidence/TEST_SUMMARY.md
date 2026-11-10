# Lab 8 — Tests executed (real runs, 2026-11-09)

Every row was executed on the development machine (Fedora, Docker 29.9.3, Compose v5.7.0). Nothing is simulated.
Items that need GitHub, Docker Hub or Render are listed at the end as **not executed**.

| # | What was tested | Command | Result | Evidence |
|---|---|---|---|---|
| 1 | Baseline test suite before any change | `pytest --cov` | ✅ 241 passed, 97 % (after creating the missing local `taller_mecanico_test` DB; before that, 98 errors) | — |
| 2 | Suite after Phase 1 (health, frontend, proxy, seed, URL normalisation) | `pytest --cov` | ✅ 257 passed, 97 % | `p1-pytest.txt` |
| 3 | OpenAPI spec unchanged by new routes | `scripts/export_openapi.py` + `git diff` | ✅ unchanged | — |
| 4 | gunicorn + entrypoint locally (migrations, `/health`, frontend, Swagger, login) | `docker/entrypoint.sh gunicorn` + `curl` | ✅ all 200 | — |
| 5 | E2E browser flow through local gunicorn | `scripts/e2e_flow.py` | ✅ appointment #11 booked → paid → tracked → completed; no CSP/JS errors | `p1-local-*.png` |
| 6 | Optimized image build | `docker build -t mecatrack:optimized .` | ✅ 42 s | — |
| 7 | Container runs, non-root, read-only code, no `.env`, health | `docker run`, `docker exec whoami`, `touch` | ✅ `app` (uid 10001), write denied, `healthy` | `p2-02-image-inspection.png` |
| 8 | Container logs clean | `docker logs` | ❌ → ✅ gunicorn 26 control-socket error; fixed with `control_socket_disable` | — |
| 9 | Path traversal through the frontend routes | `curl --path-as-is /pages/../../backend/config.py` | ✅ 404 | — |
| 10 | E2E against the container | `scripts/e2e_flow.py` | ✅ appointment #12 | — |
| 11 | Size comparison naive vs optimized | `docker images mecatrack` | ✅ 2.27 GB → 436 MB (−80.8 %); 658 → 105 MB compressed | `p2-01-docker-images.png`, `docs/docker/size-comparison.md` |
| 12 | Compose refuses to start without secrets | `docker compose config` (no `.env`) | ✅ fails with "set SECRET_KEY in .env" | — |
| 13 | Compose from zero | `docker compose down -v && docker compose up --build -d` | ✅ db and app `healthy` | `p3-01-compose-up.png`, `p3-02-app-logs.png` |
| 14 | Manual seed + login with a seed user | `scripts/dev.sh seed` + `curl /api/auth/login` | ✅ 200, role client | `p3-03-seed-and-login.png` |
| 15 | E2E against compose | `scripts/dev.sh e2e` | ❌ → ✅ first run hit 429 (login rate limit, correct behaviour); script now honours `Retry-After` | `p3-e2e-*.png` |
| 16 | Test suite against the compose database | `scripts/dev.sh test` | ✅ 257 passed | — |
| 17 | Health reflects the database | `docker compose stop db` / `start db` | ✅ 503 → 200 without restarting the app | `p3-04-health-db-down.png` |
| 18 | Lint gate | `ruff check .` | ✅ 0 findings (after 11 fixes) | `p4-02-quality-gates-local.png` |
| 19 | Code security gate | `bandit --severity-level medium` | ✅ 0 high/medium (7 justified `nosec`, 6 low reported) | `p4-02-quality-gates-local.png` |
| 20 | Dependency audit | `pip-audit -r requirements.txt` | ✅ 0 known vulnerabilities (54 packages) | `p4-02-quality-gates-local.png` |
| 21 | Workflow syntax | `actionlint 1.7.12` (+shellcheck) | ✅ 0 errors in 3 workflows | `p4-01-actionlint.png` |
| 22 | CI `test` job commands, extracted from the YAML | `bash testjob.sh` | ✅ exit 0, coverage 97.42 % ≥ 90 % | — |
| 23 | CI `build` smoke test, extracted from the YAML | `bash smoke.sh` | ✅ healthy, version = commit, user `app` | `p4-03-smoke-test-script.txt` |
| 24 | Render blueprint | JSON Schema validation (render.com/schema/render.yaml.json) | ✅ valid | — |
| 25 | JWT demo | `scripts/demo_jwt.sh` | ✅ 9/9 (200, 403, 401 × 6 incl. expired and revoked) | `p6-01-demo-jwt.png` |
| 26 | Quality report | `scripts/quality_report.sh` | ✅ all gates pass | `p6-02-quality-report.png`, `docs/quality-report.md` |
| 27 | Shell scripts | `shellcheck` | ❌ → ✅ 4 SC2164 fixed, 3 SC2016 intentional | — |
| 28 | Mermaid diagram renders | `mermaid-cli 11.4.2` | ✅ | `docs/architecture.png` |
| 29 | Slides file | `validate.py` + LibreOffice render | ✅ valid, visual QA done (2 rounds) | `docs/slides/MecaTrack_Lab8_Demo.pptx` |

## Not executed (need the team's accounts)

| What | Why | How it will be verified |
|---|---|---|
| GitHub Actions run (4 stages green) | needs a push to `main` and the secrets | Actions tab after the merge; screenshot |
| Docker Hub push | needs Docker Hub credentials | image visible at hub.docker.com |
| Render deploy hook with `imgURL` | needs the Render service | `deploy` job log + Render Events |
| Public URL `/health` and E2E | no public URL yet | `scripts/e2e_flow.py --base-url <PUBLIC_URL>` and `scripts/demo_jwt.sh <PUBLIC_URL>` |
