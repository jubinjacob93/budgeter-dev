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

## QA verdict

(QA adds its PASS or FAIL verdict here.)
