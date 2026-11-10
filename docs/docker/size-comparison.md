# Docker image size comparison

Real measurements taken on 2026-11-09 with Docker 29.9.3 (containerd image store), building both
images from the same commit. Evidence: `docs/evidence/p2-01-docker-images.png`,
`p2-02-image-inspection.png`, `p2-03-optimized-history.png` (and the matching `.txt` files).

| Image | Dockerfile | Base | Disk usage | Content size (compressed, what is pushed) | Layers | User | Health check | Files in `/app` | `.git` inside | Compiler (`gcc`) |
|---|---|---|---:|---:|---:|---|---|---:|---|---|
| `mecatrack:naive` | `docs/docker/Dockerfile.naive` | `python:3.12` (1.62 GB) | **2.27 GB** | **658 MB** | 11 | root | no | 2430 | yes | yes |
| `mecatrack:optimized` | `Dockerfile` | `python:3.12-slim` (178 MB) | **436 MB** | **105 MB** | 11 | `app` (uid 10001) | yes | 153 | no | no |
| **Reduction** | | | **−80.8 %** | **−84.0 %** | | | | **−93.7 %** | | |

```text
$ docker images mecatrack
IMAGE                 ID             DISK USAGE   CONTENT SIZE   EXTRA
mecatrack:naive       11bdb6da4ec7       2.27GB          658MB
mecatrack:optimized   a5ef3b4757da        436MB          105MB
```

## Where the savings come from

1. **Slim base image** (`python:3.12-slim` vs `python:3.12`): the full image carries compilers, headers and
   Debian tooling that a pure-wheel install never uses (~1.4 GB of the difference).
2. **Multi-stage build**: dependencies are installed into `/opt/venv` in a *builder* stage and only that
   directory (198 MB, mostly `duckdb` and `google-genai`) is copied into the runtime stage. pip, its cache
   and the build layers stay behind.
3. **`.dockerignore`**: the context only sends `backend/` code, `frontend/` and `docker/entrypoint.sh`.
   The naive image ships `.git` (94 MB), reports, documentation, screenshots, tests and mutation-testing
   output — 2430 files vs 153.
4. **Layer order**: `requirements.txt` is copied before the code, so a code change rebuilds only the last
   ~0.5 MB layers instead of reinstalling every dependency.

## Security differences (not only size)

| Aspect | Naive | Optimized |
|---|---|---|
| Process user | root | `app` (uid 10001), cannot write its own code |
| Attack surface | gcc, make, full Debian userland | no compiler, minimal userland |
| Secrets | relies on luck (`.env` would be copied without an ignore rule) | `.env` excluded by `.dockerignore` |
| Health | none — the orchestrator cannot tell a broken app | `HEALTHCHECK` on `/health` (checks the database) |

Note: the naive build was given a tiny `Dockerfile.naive.dockerignore` that excludes only `.env` and the
local `venv/` — even a first attempt must not bake secrets into an image. Everything else is copied.

## Reproduce

```bash
docker build -t mecatrack:optimized .
docker build -f docs/docker/Dockerfile.naive -t mecatrack:naive .
docker images mecatrack
```
