# 2. Run Postgres and a FastAPI skeleton in Docker Compose

Depends on: 1

## Goal

After `cp .env.example .env`, `make run` starts a Postgres service with pgvector available and a FastAPI service, and `GET /health` reports whether the API can reach the database. The `/health` endpoint is tested by unit tests (database stubbed) and by integration tests against a real Postgres, locally and in CI.

## Acceptance criteria

### Dependencies

- [ ] Runtime dependencies in `pyproject.toml` are exactly `fastapi`, `uvicorn`, `psycopg[binary]` and `pydantic-settings`. `httpx` is added to the dev group (needed by FastAPI's `TestClient`). No other dependency is added
- [ ] `uv.lock` is updated and `uv sync --locked` succeeds on a fresh clone

### Configuration

- [ ] `src/budgeter/core/config.py` defines a settings class that reads `DATABASE_URL` from environment variables only (no `.env` file loading in code). Importing the module does not fail when `DATABASE_URL` is unset; the API fails only when the setting is actually used
- [ ] `.env.example` is committed and lists every variable the stack reads: `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_PORT`, `API_PORT` and `DATABASE_URL` (the host-side URL, pointing at `localhost`). Each has a one-line comment, and the password is an obvious placeholder (e.g. `change-me`). The `DATABASE_URL` comment says it must match the `POSTGRES_*` values above.
- [ ] `.gitignore` ignores `.env` and any `.env.*` file except `.env.example`; `git check-ignore .env.local` succeeds and `git check-ignore .env.example` fails
- [ ] Running `docker compose config` without a `.env` file (and without the variables in the shell) fails with a message naming the missing `POSTGRES_PASSWORD`, rather than starting Postgres with an empty password. 
- [ ] In `docker-compose.yml`, only `POSTGRES_PASSWORD` is required (`${POSTGRES_PASSWORD:?...}`); `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_PORT` and `API_PORT` have defaults matching `.env.example` (e.g. `${API_PORT:-8000}`)

### Docker Compose

- [ ] `docker-compose.yml` defines two services, `db` and `api`
- [ ] `db` uses a pinned pgvector image tag for Postgres 17 (e.g. `pgvector/pgvector:pg17`, never `latest`), stores data in a named volume, and has a health check using `pg_isready`
- [ ] `db` publishes its port only on `127.0.0.1` (`127.0.0.1:${POSTGRES_PORT}:5432`), never on all interfaces
- [ ] `api` is built from the repository `Dockerfile` (target `api`), waits for `db` with `depends_on: condition: service_healthy`, and publishes `127.0.0.1:${API_PORT}:8000`
- [ ] Inside the `api` container, `DATABASE_URL` points at the `db` service host name (built in `docker-compose.yml` from the `POSTGRES_*` variables), not at `localhost`
- [ ] `make run` runs `docker compose up --build`, and after it starts, `docker compose ps` shows `db` as healthy and `api` as running
- [ ] `docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select name from pg_available_extensions where name = 'vector'"` returns one row
- [ ] Data survives a restart: a table created with `psql`, then `docker compose down` and `make run` again, is still there. `docker compose down -v` removes it

### Dockerfile

- [ ] A root `Dockerfile` has a named stage `api` based on `python:3.13-slim`, installs dependencies with uv from `uv.lock` (`uv sync --locked --no-dev`), and runs the app with uvicorn on port 8000
- [ ] The container runs as a non-root user (`docker compose exec api whoami` does not print `root`)
- [ ] A `.dockerignore` excludes at least `.env`, `.env.*`, `.git`, `.venv`, caches and `_docs/`, so `.env` is never copied into an image
- [ ] `docker build --target api .` succeeds without a `.env` file

### API and /health

- [ ] The FastAPI app lives in `src/budgeter/api/main.py` and includes a router from `src/budgeter/api/routers/health.py`. The database check is a function in `src/budgeter/core/database.py`; the router only calls it and shapes the response (schema in `src/budgeter/api/schemas/health.py`)
- [ ] With the database reachable, `GET /health` returns `200` and `{"status": "ok", "database": "ok"}`
- [ ] With the database unreachable (e.g. `docker compose stop db`), `GET /health` returns `503` and `{"status": "error", "database": "unavailable"}` within 5 seconds, and the API process keeps running. It returns `200` again after `docker compose start db`, without restarting `api`
- [ ] With a wrong database password, `GET /health` returns `503` with the same body
- [ ] The `503` body never contains the exception message, the database URL, the user name or the password. When the check fails, the API logs one warning that names the error type, without the database URL or password
- [ ] The API starts even when the database is down at startup (no connection is opened at import or startup)
- [ ] The database check does not block the event loop (the endpoint is a plain `def`, or it uses psycopg's async connection)
- [ ] `GET /openapi.json` lists `/health`, and `/docs` loads

### Tests

- [ ] Unit tests in `tests/unit/` cover the `200` and `503` responses with the database check stubbed through a FastAPI dependency override; they need no running database
- [ ] Integration tests in `tests/integration/` call `/health` through `TestClient` against a real Postgres: one with a valid `DATABASE_URL` (expects `200`) and one with a wrong password (expects `503`)
- [ ] Integration tests are marked `integration` (marker registered in `pyproject.toml`) and are skipped with a visible reason when `DATABASE_URL` is unset. When `DATABASE_URL` is set but the database is unreachable, they fail, not skip
- [ ] On a fresh clone without a running database, `make test` and `make lint` exit 0 (integration tests reported as skipped)
- [ ] With the stack running and `DATABASE_URL` exported from `.env`, `make test` runs the integration tests and they pass

### CI

- [ ] The CI workflow runs a Postgres service container from the same pgvector image as `docker-compose.yml`, with a health check, and sets `DATABASE_URL` for the test step, so integration tests run in CI (the job log shows them as passed, not skipped)
- [ ] CI builds the API image with `docker build --target api .`
- [ ] The service password in the workflow is a throwaway test value; no repository secret is needed
- [ ] After the human pushes, the workflow run for that commit is green

### README

- [ ] The README's Development section adds `cp .env.example .env` and `make run`, says the API is at `http://localhost:8000/health` by default, and explains how to run the integration tests locally

## Out of scope

- SQLAlchemy engine and session, Alembic, `CREATE EXTENSION vector`, `make migrate` and the CI migration step - task 3 (it reuses the CI Postgres service added here and may rewrite `core/database.py` on top of SQLAlchemy)
- Any table or schema - tasks 4 and 5
- `make seed` - task 6
- Authentication; `/health` stays public when the other endpoints are protected - task 16
- The Streamlit, MCP server and scheduler services and their Dockerfile stages - tasks 18, 31 and 24
- The read-only database role for the MCP server - task 31
- Reaching the API over Tailscale, production settings and a production Compose setup - task 55
- Backups - task 56
- `DEMO_MODE` and its variable in `.env.example` - task 53
- Environment variables for later features (Anthropic key, Plaid, encryption key, ntfy, email) - added to `.env.example` by the task that first reads them

## Constraints

- Files this task may create or change: `docker-compose.yml`, `Dockerfile`, `.dockerignore`, `.env.example`, `.gitignore`, `Makefile`, `pyproject.toml`, `uv.lock`, `README.md`, `.github/workflows/ci.yml`, `src/budgeter/core/config.py`, `src/budgeter/core/database.py`, `src/budgeter/api/main.py`, `src/budgeter/api/routers/` and `src/budgeter/api/schemas/`, any missing `__init__.py` files under `src/budgeter/`, and test files (including `conftest.py`) under `tests/unit/` and `tests/integration/` (remove `tests/integration/.gitkeep` once a real file is there).. Do not touch `_docs/` except to add implementation notes to this file.
- Dependencies: the human approves the ones listed above by approving this groomed task (AGENTS.md: no dependencies without asking). Do not add others, including pytest plugins or `uvicorn[standard]` extras.
- Do not use SQLAlchemy yet; the health check uses psycopg directly with a short `connect_timeout`. Task 3 introduces SQLAlchemy.
- Follow `_docs/plan.md` § 5 (Architecture: one image per service, built from this codebase; Code conventions: routers handle HTTP only, logic in service modules) and § 8 (secrets only in environment variables; `.env` git-ignored; `.env.example` committed).
- Postgres stays internal: no port published on `0.0.0.0` for `db` or `api`.
- Never commit `.env`, a real password or any financial data.
- Pin GitHub Actions to a major version tag, as in task 1. Keep `make lint` and `make test` as the CI entry points.
- Commit with messages that start with `task 02:`. Do not push; the human pushes and checks the CI run.
- If `get_settings()` is cached, tests that change `DATABASE_URL` clear the cache before and after (`get_settings.cache_clear()`).

## Implementation notes

- Dependencies resolve to fastapi 0.156.4, uvicorn 0.54.0, psycopg[binary] 3.3.6 and pydantic-settings 2.16.1, plus httpx 0.28.1 in the dev group. `uv tree --no-dev --depth 1` shows only those four.
- Layout: `core/config.py` (`Settings` with one required `database_url`, plus a cached `get_settings()`; no `env_file`), `core/database.py` (`check_database(url) -> bool`, psycopg with `connect_timeout=2`), `api/schemas/health.py`, `api/routers/health.py` and `api/main.py`. The router has one dependency, `database_is_reachable`, which unit tests override. The endpoint is a plain `def`, so it runs in the thread pool. On failure the check logs `Database check failed: <ErrorType>` and nothing else.
- Image: `pgvector/pgvector:0.8.7-pg17`, the newest pg17 tag on Docker Hub. It pins pgvector as well as the Postgres major. CI uses the same tag. When bumping it, change both files.
- The Dockerfile copies uv from `ghcr.io/astral-sh/uv:0.13.0`, matching the local uv. It runs `uv sync --locked --no-dev` in two layers (dependencies first, then the project with `--no-editable`) and runs as user `app` (uid 10001). `.dockerignore` also excludes `tests/`, `evals/`, `.github/`, `.claude/` and `old versions/`. The image contains only `.venv`, `src`, `pyproject.toml`, `uv.lock` and `README.md`. `README.md` is needed because `uv_build` reads it.
- `POSTGRES_PASSWORD:?` appears twice in `docker-compose.yml`, in `db` and in the `api` `DATABASE_URL`, so `docker compose config` without `.env` prints the missing-variable message twice. The password is put into a URL unescaped. `.env.example` therefore says to use only letters, digits, `-` and `_`.
- pytest runs with `addopts = "-rs"`, so skip reasons are printed in the summary. Integration tests skip at module level with `skipif(not DATABASE_URL)`. If the URL is set but the database is unreachable, they fail on the status code. The wrong-password test changes the password in `DATABASE_URL` and clears `get_settings` before and after.
- The unit test for importing without `DATABASE_URL` runs in a subprocess. An `importlib.reload` would swap `get_settings` for modules that already imported it.
- Verified locally (Docker 29.8.2, Compose v5.6.0, WSL2): `make run` puts `db` healthy and `api` up, with both ports on `127.0.0.1` only. `whoami` prints `app`. The `pg_available_extensions` query returns one row. `/openapi.json` lists `/health` and `/docs` returns 200. A table survives `down` and `make run` and is gone after `down -v`. With `docker compose stop db`, `/health` returns 503 and returns 200 again after `start db` without restarting `api`. The API starts and returns 503 when it is started with `--no-deps` and no db. The API log shows only `Database check failed: OperationalError` (no URL, user or password). With `.env` exported, `make test` gives 11 passed. On a fresh clone without `DATABASE_URL`: `uv sync --locked` works, `make test` gives 9 passed and 2 skipped, `make lint` passes and `docker build --target api .` succeeds.
- **For the reviewer: the 5-second limit has little margin on this machine.** With `db` stopped, `/health` took 3.1–4.0 s (five tries). Nearly all of it is the DNS lookup of `db`: Docker drops the record when the container stops, and the query is forwarded upstream (the WSL resolver here) before it fails. psycopg's `connect_timeout` does not shorten this, and 2 s is already libpq's minimum. On a host with a faster resolver it should be lower. It meets the limit here, but a slow upstream resolver could push it over 5 s.
- Starlette prints a `StarletteDeprecationWarning` that recommends `httpx2` over `httpx` for `TestClient`. The task specifies `httpx`, so I kept it. It is only a warning.
- Not verified: the green CI run on GitHub. The human needs to push first.

## QA verdict

(QA adds its PASS or FAIL verdict here.)
