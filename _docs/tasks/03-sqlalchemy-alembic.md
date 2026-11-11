# 3. Set up SQLAlchemy and Alembic

Depends on: 2

## Goal

The app reaches Postgres through one SQLAlchemy 2.0 engine and session factory built from `DATABASE_URL`. `/health` uses that engine too. Alembic manages the schema from `migrations/`, and its first migration enables the `vector` extension. `make migrate` applies migrations to the Compose database. CI applies every migration to a fresh Postgres, rolls them back, applies them again, and checks that the models and migrations match.

## Acceptance criteria

### Dependencies

- [ ] Runtime dependencies in `pyproject.toml` are exactly the four from task 2 plus `sqlalchemy` (2.0 or later) and `alembic`. No other dependency is added, including `psycopg2`, `pgvector` or `asyncpg`
- [ ] `uv.lock` is updated and `uv sync --locked` succeeds on a fresh clone

### Engine and session (`src/budgeter/core/database.py`)

- [ ] `get_engine()` returns one SQLAlchemy `Engine` built from `get_settings().database_url`. It is created on first use and reused after that. Importing `budgeter.core.database` or `budgeter.api.main` with `DATABASE_URL` unset neither fails nor opens a connection (the existing subprocess import test is extended to cover `budgeter.core.database`)
- [ ] The engine always uses the psycopg 3 driver: a `DATABASE_URL` that starts with `postgresql://` or with `postgresql+psycopg://` gives an engine whose `url.drivername` is `postgresql+psycopg`. `.env.example` and the Compose `DATABASE_URL` keep the plain `postgresql://` form. A unit test covers both forms without a database
- [ ] The engine uses `pool_pre_ping=True` and a 2-second `connect_timeout`, so a connection left in the pool from before a database restart does not cause an error
- [ ] Tests can reset the cached engine (for example `get_engine.cache_clear()`), and any test that changes `DATABASE_URL` resets both the settings and the engine before and after
- [ ] A session factory (`sessionmaker`, `expire_on_commit=False`) is bound to the engine, and a FastAPI-style dependency `get_session()` yields a `Session` and closes it afterwards, also when the caller raises. No endpoint uses it yet. An integration test runs `select 1` through `get_session()`
- [ ] The engine is synchronous (no `create_async_engine`); endpoints that use it stay plain `def`
- [ ] SQL echo is off, and nothing in this module logs or returns the database URL or password

### Declarative base (`src/budgeter/core/models/`)

- [ ] `src/budgeter/core/models/base.py` defines `Base` (a SQLAlchemy 2.0 `DeclarativeBase`) whose `metadata` has a naming convention with the keys `ix`, `uq`, `ck`, `fk` and `pk`, so constraint names in later migrations are predictable. `src/budgeter/core/models/__init__.py` re-exports `Base`. Later tasks import their models there so Alembic sees them
- [ ] No tables are defined: `Base.metadata.tables` is empty

### /health on SQLAlchemy

- [ ] `check_database` runs `select 1` through the SQLAlchemy engine instead of `psycopg.connect`. The router, the response schema and the `database_is_reachable` dependency keep their roles from task 2
- [ ] Every `/health` criterion from task 2 still holds, and the existing unit and integration tests pass, adapted only to the new signature or engine reset: `200` with `{"status": "ok", "database": "ok"}` when the database is reachable; `503` with `{"status": "error", "database": "unavailable"}` when it is stopped (within 10 seconds) or the password is wrong; the API starts with the database down; it returns `200` again after `docker compose start db` without restarting `api`
- [ ] On failure the API logs one warning that names only the error type (e.g. `Database check failed: OperationalError`). The message never contains the URL, user name, host or password; the existing log test still checks this

### Alembic

- [ ] `alembic.ini` is at the repository root, `script_location` points at `migrations/`, and `sqlalchemy.url` is not set in the file
- [ ] `migrations/env.py` gets the connection from `budgeter.core.database.get_engine()` (or `get_settings().database_url`) and does not put the URL into the Alembic config with `set_main_option`, so a `%` in a URL-encoded password cannot break config interpolation. `target_metadata` is `Base.metadata`, imported from `budgeter.core.models`
- [ ] Migration files are named `<rev>_<slug>.py` (`file_template` in `alembic.ini`), and revision IDs are four-digit sequence numbers set with `--rev-id`. The first migration is `migrations/versions/0001_enable_vector_extension.py` with revision `0001` and `down_revision = None`
- [ ] Revision `0001` upgrades with `CREATE EXTENSION IF NOT EXISTS vector` and downgrades with `DROP EXTENSION IF EXISTS vector`. It creates no tables
- [ ] On a fresh database, `uv run alembic upgrade head` (with `DATABASE_URL` exported) exits 0. After it, `select extname from pg_extension where extname = 'vector'` returns one row, and `alembic current` prints `0001 (head)`
- [ ] Running `alembic upgrade head` a second time exits 0 and changes nothing. 
- [ ] `alembic downgrade base` exits 0 and removes the extension. A later `alembic upgrade head` exits 0 again
- [ ] `alembic check` exits 0 (no difference between the models and the migrations)
- [ ] With `DATABASE_URL` unset, `uv run alembic upgrade head` exits non-zero with an error that names `DATABASE_URL` or `database_url` and does not try to connect anywhere
- [ ] With the database unreachable or the password wrong, `alembic upgrade head` exits non-zero within 15 seconds, and its output does not contain the password
- [ ] `migrations/` passes `make lint` (generated files are formatted with Ruff)

### make migrate and Docker

- [ ] `make migrate` runs `docker compose run --rm api alembic upgrade head`. It starts `db` if needed (through `depends_on`), uses the `DATABASE_URL` that Compose gives `api` (host `db`), and needs no variables exported in the host shell
- [ ] After `docker compose down -v`, `make run` (in one terminal) and `make migrate` (in another) exit 0. After that, the `vector` row is in `pg_extension`. Running `make migrate` again exits 0
- [ ] The `api` image contains `alembic.ini` and `migrations/`. `.dockerignore` does not exclude them, and the container still runs as the non-root user `app`
- [ ] The API container does not run migrations on startup. `make run` behaves as in task 2

### Tests

- [ ] Unit tests (no database) cover: driver normalization for both URL forms; the engine not being created at import; the naming convention keys on `Base.metadata`; and the `/health` 200, 503 and log tests from task 2
- [ ] Integration tests in `tests/integration/` (marked `integration`, skipped with a visible reason when `DATABASE_URL` is unset, failing when it is set but the database is unreachable) cover: `alembic upgrade head` through Alembic's Python API (`alembic.command.upgrade` with the repository's `alembic.ini`), followed by checks that the `vector` extension exists and that the database revision equals the script head; `select 1` through `get_session()`; and the `/health` integration tests from task 2
- [ ] Integration tests never run `downgrade`, so running them against the local development database never removes data
- [ ] On a fresh clone without a database, `make test` and `make lint` exit 0 (integration tests skipped). With the stack running and `.env` exported, `make test` passes with the integration tests run

### CI

- [ ] `.github/workflows/ci.yml` has a `Migrate` step that runs before `Test` against the existing Postgres service container, with the same `DATABASE_URL`. It runs, in order and with no `continue-on-error`: `uv run alembic upgrade head`, `uv run alembic downgrade base`, `uv run alembic upgrade head` and `uv run alembic check`
- [ ] A migration that fails to upgrade or downgrade fails the workflow
- [ ] After the human pushes, the workflow run for that commit is green, and the log shows the `Migrate` step and the integration tests passing (not skipped)

### Documentation

- [ ] `AGENTS.md` is not changed (`make migrate` is already listed there)

## Out of scope

- Any table or model (users, connections, accounts) - task 4
- Transaction and category tables, the `pgvector` Python package and the `merchants.embedding` vector column - task 5
- `make seed` and seed data - task 6
- The read-only database role for the MCP server, and a separate migration role with fewer privileges than the Compose superuser - task 31
- Running migrations automatically on deploy or at container start, and production database settings - task 55
- Loading seed data and running migrations in `DEMO_MODE` - task 53
- Async SQLAlchemy - not planned. The plan doesn't need it, and plain `def` endpoints already run in the thread pool
- Changing the `/health` response shape or making it check the migration revision - not planned
- A "Migrations" section in the README - task 54
- Offline mode (`alembic upgrade head --sql`) - not planned

## Constraints

- Files this task may create or change: `pyproject.toml`, `uv.lock`, `alembic.ini`, `migrations/` (`env.py`, `script.py.mako`, `versions/`), `src/budgeter/core/database.py`, `src/budgeter/core/models/` (`__init__.py`, `base.py`), `src/budgeter/api/routers/health.py` (only if the dependency must change), `Makefile`, `Dockerfile`, `.dockerignore`, `.github/workflows/ci.yml`, `README.md`, and tests under `tests/unit/` and `tests/integration/` (including `conftest.py`). Do not touch `_docs/` except to add implementation notes to this file.
- Dependencies: the human approves `sqlalchemy` and `alembic` by approving this groomed task (AGENTS.md: no dependencies without asking). Do not add others, including pytest plugins or SQLAlchemy extras.
- Follow `_docs/plan.md` § 5 (Repository layout: `core/` holds config, database session and shared models; `migrations/` at the root; Code conventions: models map to the database, routers handle HTTP only; Library defaults: SQLAlchemy 2.0), § 9 (CI runs Alembic migrations on a fresh database) and § 10 (every schema change goes through Alembic).
- Use SQLAlchemy 2.0 style only (`DeclarativeBase`, `select()`, `Session` as a context manager), not the legacy `declarative_base()` or `Query` API.
- Configuration comes only from environment variables through `core/config.py`. Do not load `.env` in code, in `alembic.ini` or in `env.py`.
- Never print, log or put the database URL or password into exception messages, Alembic output or test failure messages.
- Keep the pgvector image tag `pgvector/pgvector:0.8.7-pg17` the same in `docker-compose.yml` and CI.
- Pin GitHub Actions to a major version tag. Keep `make lint` and `make test` as the CI entry points.
- Commit with messages that start with `task 03:`. Do not push; the human pushes and checks the CI run.

## Implementation notes

- **Dependencies:** added `sqlalchemy>=2.1.8` and `alembic>=1.20.1` with `uv add`. `mako` and `markupsafe` come in transitively. No other runtime dependency was added.
- **`core/database.py`:** `psycopg_url()` forces `postgresql+psycopg`, and `build_engine(url)` creates an engine (`pool_pre_ping=True`, `connect_timeout=2`, `echo=False`) without connecting. `get_engine()` is `lru_cache`d around `build_engine(get_settings().database_url)`. The session factory is cached per engine (`_session_factory(engine)`, `maxsize=1`), so `get_engine.cache_clear()` alone also gives a fresh factory. `get_session()` uses the session as a context manager, so it closes when the caller raises.
- **`check_database` signature changed** from `(database_url: str)` to `(engine: Engine)`. `database_is_reachable` now calls `check_database(get_engine())`. It catches `SQLAlchemyError`, and the logged name is still `OperationalError`.
- **Alembic:** `env.py` uses `get_engine().connect()` and never `set_main_option`. It calls `fileConfig(..., disable_existing_loggers=False)` so that running Alembic from pytest doesn't silence the app's loggers (that would break the caplog test). Offline mode exits with a clear message. `alembic.ini` has post-write hooks that run `ruff check --fix` and `ruff format` on new revisions. **Note:** the fix hook removes the template's `op`/`sa` imports when a revision is empty, so add `from alembic import op` back when you fill one in (as in `0001`). Create revisions with `uv run alembic revision -m "..." --rev-id 000N`.
- **`.dockerignore`:** `__pycache__/` and `*.pyc` became `**/__pycache__/` and `**/*.pyc`. The old patterns matched only the root, so a host `migrations/versions/__pycache__` was copied into the image.
- **README:** one `make migrate` line under "Running the stack". I didn't add a Migrations section (task 54).
- **Tests:** `tests/unit/test_database.py` covers driver normalization for both forms, engine reuse and settings, the session factory following an engine reset, `get_session` closing on an exception, no engine created at import (subprocess), and the naming convention with no tables. The subprocess import test in `test_config.py` now also imports `budgeter.core.database`. `tests/integration/conftest.py` resets settings and engine around every integration test. New `test_migrations.py` (upgrade only, never downgrade) and `test_session.py`.
- **Checked by hand (WSL2):**
  - Fresh throwaway `pgvector/pgvector:0.8.7-pg17` container: `upgrade head` gives exit 0, one `vector` row and `0001 (head)`. A second upgrade exits 0. `downgrade base` exits 0 and leaves 0 rows. Upgrading again exits 0, and `alembic check` exits 0.
  - `DATABASE_URL` unset gives exit 1 with a pydantic error naming `database_url`.
  - Port 1 and a wrong password both exit 1 in under 1 s, with no password in the output; a `%25` in the password works.
  - `make migrate` runs twice with exit 0 and no host `DATABASE_URL`.
  - The image runs as `app` and contains `alembic.ini` and `migrations/`.
  - `/health` gives 200. With `db` stopped it gives 503 in 7.9 s, the same WSL DNS delay QA found in task 2. It returns 200 after `start db` without restarting `api`.
  - `make test` passes against the dev stack (21 passed) and on a fresh clone without a database (17 passed, 4 skipped). `make lint` passes.
- **Not done by me:** `docker compose down -v`, because it would delete the existing dev volume `budgeter-dev_db-data`. I covered the fresh-database criteria with a throwaway container instead; QA or the human can run the `down -v` check. The CI run can only be checked after the push.

## QA verdict: PASS

Tested `task-03` at `0a6faf6` in a fresh clone. Docker checks ran in Compose project `budgeterqa` (host ports 55432 and 58000, a throwaway `.env` in the clone only). The dev volume `budgeter-dev_db-data` was not touched.

### Dependencies

- [x] Runtime deps are exactly `fastapi`, `psycopg[binary]`, `pydantic-settings`, `uvicorn`, `sqlalchemy>=2.1.8`, `alembic>=1.20.1` - PASS
      The diff against `main` adds only these two. `uv.lock` has no `psycopg2`, `pgvector` or `asyncpg`
- [x] `uv.lock` updated, `uv sync --locked` succeeds on a fresh clone - PASS (exit 0)

### Engine and session

- [x] `get_engine()` is cached and created on first use; importing `budgeter.core.database` and `budgeter.api.main` without `DATABASE_URL` works and opens no connection - PASS
      The subprocess test in `test_config.py` covers `budgeter.core.database`. `test_database.py` also checks `cache_info().currsize == 0` after import
- [x] Both URL forms give `postgresql+psycopg`; `.env.example` and Compose keep plain `postgresql://` - PASS (unit test covers both forms)
- [x] `pool_pre_ping=True`, `connect_timeout=2` - PASS
      With a blackholed host (10.255.255.1), `alembic upgrade head` failed in 2.7 s. `/health` went back to 200 after `start db` with no error from stale pooled connections
- [x] The engine can be reset; tests that change `DATABASE_URL` reset settings and engine before and after - PASS (`tests/integration/conftest.py`, `tests/unit/test_database.py` fixtures)
- [x] `sessionmaker(expire_on_commit=False)`; `get_session()` closes the session also when the caller raises; no endpoint uses it; an integration test runs `select 1` - PASS
- [x] Synchronous engine, plain `def` endpoint - PASS (no `create_async_engine` anywhere)
- [x] Echo off; the URL and password are never logged or returned - PASS

### Declarative base

- [x] `Base(DeclarativeBase)` with naming convention keys `ix`, `uq`, `ck`, `fk`, `pk`, re-exported from `models/__init__.py` - PASS
- [x] `Base.metadata.tables` is empty - PASS

### /health on SQLAlchemy

- [x] `check_database` runs `select 1` through the engine; the router, schema and `database_is_reachable` keep their roles - PASS
- [x] Task 2 `/health` behaviour holds - PASS
      200 `{"status":"ok","database":"ok"}` when the database is up. With `db` stopped: 503 `{"status":"error","database":"unavailable"}` in 4.0 s. Wrong password: 503 (integration test). `docker compose restart api` with `db` stopped: the API starts and serves 503. After `docker compose start db`: 200 with the same `api` `StartedAt`. The only test changes are the signature change and the engine reset
- [x] Failure logs only the error type - PASS
      The API log has `Database check failed: OperationalError` (22 times) and no password, user or URL. The unit log test still checks this

### Alembic

- [x] `alembic.ini` at the root, `script_location` is `migrations/`, no `sqlalchemy.url` - PASS
- [x] `env.py` uses `get_engine()` and no `set_main_option`; `target_metadata = Base.metadata` from `budgeter.core.models` - PASS
      A role with password `a%b` (URL `a%25b`) ran `alembic current` with exit 0
- [x] `file_template = %%(rev)s_%%(slug)s`; `0001_enable_vector_extension.py`, revision `0001`, `down_revision = None` - PASS
- [x] Upgrade uses `CREATE EXTENSION IF NOT EXISTS vector`, downgrade uses `DROP EXTENSION IF EXISTS vector`, no tables - PASS
- [x] Fresh database: `upgrade head` exits 0, one `vector` row, `alembic current` prints `0001 (head)` - PASS
- [x] A second `upgrade head` exits 0 and runs nothing (no "Running upgrade" line, still one row) - PASS
- [x] `downgrade base` exits 0 and leaves 0 `vector` rows; a later `upgrade head` exits 0 with 1 row - PASS
- [x] `alembic check` exits 0 ("No new upgrade operations detected.") - PASS
- [x] `DATABASE_URL` unset: exit 1 with a pydantic error naming `database_url`, raised before an engine exists - PASS
      Not checked at syscall level (no `strace`). Settings fail before `build_engine` runs, so no connection is possible
- [x] Unreachable or wrong password: non-zero within 15 s, no password in output - PASS
      Port 1: exit 1 in 0.7 s. Blackholed host: exit 1 in 2.7 s. Wrong password: exit 1 in 0.5 s. The password was absent from the output in all three
- [x] `migrations/` passes `make lint` - PASS

### make migrate and Docker

- [x] `make migrate` runs `docker compose run --rm api alembic upgrade head`, starts `db` through `depends_on` and needs no host `DATABASE_URL` - PASS
      With the whole `budgeterqa` stack down, `make migrate` created and started `budgeterqa-db-1` and exited 0
- [x] After `docker compose down -v`: `make run` and `make migrate` exit 0, the `vector` row is present, a second `make migrate` exits 0 - PASS
      Ran `down -v` in `budgeterqa`, `make run` in the background, then `make migrate` twice (exit 0 both times; the first ran `-> 0001`, the second ran nothing). `pg_extension` has `vector`, and `alembic_version` is `0001`. `make run` exited 0 at `down`
- [x] The image contains `alembic.ini` and `migrations/`, `.dockerignore` doesn't exclude them, and the container runs as `app` - PASS (`whoami` gives `app`; no `__pycache__` in `migrations/versions`)
- [x] The API doesn't migrate on startup - PASS
      After `make run` on a fresh volume, `/health` was 200, but there was no `vector` extension and no `alembic_version` table until `make migrate`

### Tests

- [x] Unit tests cover driver normalization (both forms), no engine at import, naming convention keys, and `/health` 200, 503 and log - PASS
- [x] Integration tests are marked, skip with a visible reason when `DATABASE_URL` is unset, and fail when the database is unreachable; they cover `command.upgrade` with the repo `alembic.ini` plus checks for `vector` and the revision against the script head, `select 1` via `get_session()`, and the task 2 `/health` tests - PASS
      With `DATABASE_URL` pointing at port 1: 3 failed and 1 passed (the wrong-password test, which expects 503 anyway)
- [x] Integration tests never run `downgrade` - PASS (the only match is a comment)
- [x] Fresh clone without a database: `make test` and `make lint` exit 0 with integration skipped; with the stack up and `.env` exported, `make test` runs the integration tests - PASS

### CI

- [x] The `Migrate` step runs before `Test` with the same `DATABASE_URL`: upgrade, downgrade base, upgrade, check, with `set -e` and no `continue-on-error` - PASS
- [x] A failing migration fails the workflow - PASS
      Checked by reading the workflow: `set -e`, the default `bash -e` shell and no `continue-on-error`. No broken migration was run
- [x] The CI run for `0a6faf6` is green; the log shows Migrate (upgrade, downgrade, upgrade, "No new upgrade operations detected.") and the integration tests passing, not skipped - PASS (run 42560997114, 21 passed; PR run 42561293007 also green)

### Documentation

- [x] `AGENTS.md` unchanged - PASS (not in the diff against `main`; all changed files are on the allowed list)

### Other

- No secrets, `.env`, tokens or real financial data are committed. Passwords in the repo are the placeholders `change-me` and `ci-throwaway-password` and test strings.
- Gaps (not failures): 503 with `db` stopped and recovery after `start db` are checked by hand only, as in task 2. No automated test runs `upgrade head` twice.

Tests:
- `make test` on a fresh clone without `DATABASE_URL`: 17 passed, 4 skipped, 0 failed
- `make test` with the `budgeterqa` stack up and `.env` exported: 21 passed, 0 skipped, 0 failed
- `make lint`: passed
