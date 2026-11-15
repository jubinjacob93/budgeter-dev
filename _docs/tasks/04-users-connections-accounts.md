# 4. Create the users, connections and accounts tables

Depends on: 3

## Goal

`users`, `connections` and `accounts` exist as SQLAlchemy 2.0 models in `src/budgeter/core/models/` and as Alembic migration `0002`. Every account belongs to exactly one connection, every connection to exactly one user, and every account carries an `owner_tag` (`mine` / `partner` / `joint`). The database rejects bad values: unknown enum values, duplicate emails, orphaned rows and duplicate provider accounts. Integration tests insert sample rows and read them back without leaving data in the development database.

## Acceptance criteria

### Decisions this task records

- [ ] `owner_tag` is stored **relative to the user who owns the account's connection** (`connections.user_id`): `mine` means that user's account, `partner` means the other household member's, and `joint` means shared.  In practice, a household-wide import (seed, CSV or Monarch export) sits under one user's connection, and the other member's accounts in it must be tagged `partner` rather than the default `mine`. Turning this into "Mine / Partner" for whoever is viewing is a query concern (tasks 17 and 43), not a column. `_docs/plan.md` § 6 is updated: the `accounts` row note explains this meaning, and the `users`, `connections` and `accounts` rows list the columns this task adds (see below)
- [ ] Every account has a connection, including accounts from seed data, CSV and Monarch imports. Those sources get a connection row with their own `provider` value and no token. `accounts.connection_id` is `NOT NULL`

### Models (`src/budgeter/core/models/`)

- [ ] Models are written in SQLAlchemy 2.0 style (`Mapped[...]`, `mapped_column`) on the existing `Base`, one module per table (`user.py`, `connection.py`, `account.py`), with the string enums in `enums.py`. `models/__init__.py` re-exports `Base`, `User`, `Connection`, `Account` and the three enums, so Alembic sees all three tables
- [ ] The enums are Python `enum.StrEnum` classes with lowercase values:
  - `Provider`: `seed`, `csv`, `monarch`, `plaid`, `simplefin`
  - `ConnectionStatus`: `active`, `login_required`, `error`, `disconnected`
  - `AccountType`: `checking`, `savings`, `credit_card`, `brokerage`, `retirement`, `loan`, `other`
  - `OwnerTag`: `mine`, `partner`, `joint`
- [ ] Enum columns are `VARCHAR` with a named `CHECK` constraint (`sa.Enum(..., native_enum=False, create_constraint=True, name=..., values_callable=...)` or an equivalent explicit `CheckConstraint`). No native Postgres `ENUM` type is created. The database stores the lowercase **values** (for example `credit_card`), not the Python member names (`CREDIT_CARD`); a raw-SQL test checks this
- [ ] Relationships: `User.connections` ↔ `Connection.user` and `Connection.accounts` ↔ `Account.connection`, with `back_populates`. No cascade deletes from the ORM side

### `users`

- [ ] Columns: `id` (integer identity primary key), `email` (`VARCHAR(320)`, `NOT NULL`, unique), `password_hash` (`VARCHAR(255)`, `NOT NULL`), `created_at` (`timestamptz`, `NOT NULL`, server default `now()`)
- [ ] Emails are unique regardless of case: a `CHECK (email = lower(email))` constraint plus a plain unique constraint on `email`. Inserting `Alice@example.com` fails the check, and inserting `alice@example.com` twice fails the unique constraint. (Lower-casing input before saving is task 16's job; this task only enforces it in the database)
- [ ] No limit on the number of users is enforced here (see Out of scope)

### `connections`

- [ ] Columns: `id` (integer identity primary key), `user_id` (FK to `users.id`, `NOT NULL`, `ON DELETE RESTRICT`, indexed), `provider` (`Provider`, `NOT NULL`), `encrypted_token` (`BYTEA`, nullable), `status` (`ConnectionStatus`, `NOT NULL`, server default `active`), `created_at` (`timestamptz`, `NOT NULL`, server default `now()`)
- [ ] `encrypted_token` can be `NULL` (seed, CSV and Monarch connections have none). Nothing in this task writes a real or fake-real token; tests use obviously fake bytes such as `b"not-a-real-token"`
- [ ] `repr()` of a `Connection` does not contain the `encrypted_token` value (a unit test checks this with a token set)
- [ ] A user can have several connections, including several with the same provider (two Plaid logins at different institutions)

### `accounts`

- [ ] Columns: `id` (integer identity primary key), `connection_id` (FK to `connections.id`, `NOT NULL`, `ON DELETE RESTRICT`, indexed), `provider_account_id` (`VARCHAR(255)`, `NOT NULL`), `name` (`VARCHAR(255)`, `NOT NULL`), `type` (`AccountType`, `NOT NULL`), `owner_tag` (`OwnerTag`, `NOT NULL`, server default `mine`), `balance` (`NUMERIC(14, 2)`, nullable), `currency` (`CHAR(3)`, `NOT NULL`, server default `USD`), `created_at` (`timestamptz`, `NOT NULL`, server default `now()`)
- [ ] `(connection_id, provider_account_id)` is unique, so re-importing the same provider account cannot create a duplicate (task 9 upserts on it). The same `provider_account_id` under two different connections is allowed
- [ ] `balance` is `NULL` until the first sync and is never a float: a value such as `Decimal("-1234.56")` reads back as exactly `Decimal("-1234.56")`
- [ ] Inserting an account without `owner_tag` gives `mine`; inserting one without `currency` gives `USD`

### Constraint names

- [ ] Every primary key, foreign key, unique and check constraint and every index in migration `0002` has an explicit name that follows the naming convention in `core/models/base.py` (for example `pk_users`, `fk_accounts_connection_id_connections`, `uq_users_email`). A unit test inspects `Base.metadata` and finds no constraint or index with a `None` name on the three tables

### Migration `0002`

- [ ] `migrations/versions/0002_create_users_connections_accounts.py`, revision `0002`, `down_revision = "0001"`, created with `uv run alembic revision --autogenerate -m "create users connections accounts" --rev-id 0002` and then reviewed by hand (the `op` / `sa` imports restored if the Ruff hook stripped them)
- [ ] Upgrade creates the three tables with the columns, defaults and constraints above; downgrade drops them in reverse dependency order and leaves the `vector` extension in place
- [ ] On a fresh database: `alembic upgrade head` exits 0 and `alembic current` prints `0002 (head)`; `alembic downgrade 0001` exits 0 and leaves no `users`, `connections` or `accounts` table and no leftover enum type; `alembic upgrade head` exits 0 again; `alembic check` exits 0
- [ ] On a database already at `0001` (the existing dev database), `make migrate` exits 0 and moves it to `0002` without touching anything else
- [ ] The existing CI `Migrate` step (upgrade, downgrade base, upgrade, check) passes unchanged

### Tests

- [ ] Unit tests (no database) check: the three tables are in `Base.metadata` with the columns above; the enum values listed above; constraint names (see Constraint names); `repr(Connection)` without the token
- [ ] Integration tests in `tests/integration/` (marked `integration`, skipped with a visible reason when `DATABASE_URL` is unset, like the existing ones) make sure the schema is at head before they run (for example a session-scoped fixture calling `alembic.command.upgrade(config, "head")`), and run each test inside a transaction that is rolled back afterwards, so running them against the development database leaves no rows behind. A check after the run shows `select count(*) from users` unchanged.  Because Postgres aborts the whole transaction after a failed statement, the test session uses `join_transaction_mode="create_savepoint"` (or wraps each statement that is expected to fail in `session.begin_nested()`), so one `IntegrityError` does not break the rest of the test
- [ ] Integration tests cover, each as its own test:
  - insert one user, one connection and two accounts through the ORM, commit within the test transaction, and read them back in a new query (including through the relationships), with all fields equal
  - two users, each with their own connection, and accounts tagged `mine`, `partner` and `joint`; a query by `owner_tag` returns the expected accounts. One connection holds both a `mine` and a `partner` account
  - raw SQL shows the stored strings are lowercase values (`credit_card`, `joint`, `plaid`, `active`)
  - an unknown `owner_tag`, `type`, `provider` or `status` inserted with raw SQL raises `IntegrityError` (check constraint)
  - a duplicate email and an upper-case email each raise `IntegrityError`
  - an account with a `connection_id` that does not exist, and a connection with a `user_id` that does not exist, each raise `IntegrityError`
  - deleting a user that has a connection, and a connection that has accounts, each raise `IntegrityError` (`RESTRICT`). The delete is raw SQL (`DELETE FROM users WHERE id = ...`), not `session.delete()`, so the test proves the database constraint and not the ORM's own NULL-ing of the foreign key
  - a duplicate `(connection_id, provider_account_id)` raises `IntegrityError`; the same `provider_account_id` on another connection succeeds
  - a connection with `encrypted_token = NULL` and one with fake bytes both round-trip
  - `balance` `NULL` and `Decimal("-1234.56")` round-trip exactly; defaults for `owner_tag`, `currency`, `status` and `created_at` are filled by the database
- [ ] On a fresh clone without a database, `make test` and `make lint` exit 0 (integration tests skipped). With the stack running, `make migrate` run and `.env` exported, `make test` passes with the integration tests run
- [ ] The CI run for the pushed commit is green and shows the new integration tests passing, not skipped

## Out of scope

- Password hashing, login, lower-casing emails on input and the limit of two users per household - task 16
- The encryption helper for `connections.encrypted_token` and Plaid-specific columns such as the Item ID - task 21
- Provider error details on connections (error code or message) - task 22
- `last_synced_at` and sync bookkeeping on connections - task 24
- Institution name and display fields for the accounts page - task 48 (add with a migration there if needed)
- Translating `owner_tag` into "Mine / Partner / Joint" for the current viewer, and filtering by it - tasks 17 and 43
- Balance sign conventions for credit cards and loans in net worth (this task stores the balance as the provider reports it) - task 26
- Holdings and `balance_as_of` history - tasks 9 and 26
- Transaction, merchant and category tables - task 5
- Seed users and accounts - task 6
- API endpoints or schemas for these tables - tasks 16, 17 and 48
- Closing or hiding accounts, and multi-currency conversion - not planned for v1
- The read-only database role for the MCP server - task 31

## Constraints

- Files this task may create or change: `src/budgeter/core/models/` (`__init__.py`, `enums.py`, `user.py`, `connection.py`, `account.py`), `migrations/versions/0002_create_users_connections_accounts.py`, tests under `tests/unit/` and `tests/integration/` (including `conftest.py`), and `_docs/plan.md` § 6 (the three table rows only). Do not touch other `_docs/` files except to add implementation notes to this file.
- No new dependencies (AGENTS.md). Use SQLAlchemy and Alembic as installed in task 3; do not add `pgvector`, pytest plugins or factory libraries.
- SQLAlchemy 2.0 style only (`DeclarativeBase`, `Mapped`, `mapped_column`, `select()`), no legacy `Query` API. The engine stays synchronous.
- Every schema change goes through this Alembic migration (plan § 10). Do not create tables with `Base.metadata.create_all()` anywhere, including tests.
- Money is `NUMERIC` / `Decimal`, never `float`.
- No secrets in git: no real tokens, emails or financial data in tests or migrations. Use `example.com` emails and obviously fake token bytes.
- The MCP server and agent stay read-only (AGENTS.md); nothing in this task grants write access to any role.
- Follow `_docs/plan.md` § 2 (household model, ownership tags), § 5 (Repository layout: shared models in `core/`; Code conventions: models map to the database) and § 6 (data model).
- Commit with messages that start with `task 04:`. Do not push; the human pushes and checks the CI run.

## Implementation notes

- **Models**: `user.py`, `connection.py`, `account.py` and `enums.py` in `core/models/`. `enums.string_enum()` builds the shared column type: `sa.Enum(..., native_enum=False, create_constraint=True, values_callable=...)`. It gives a `VARCHAR` sized to the longest value plus a CHECK constraint named `ck_<table>_<column>`. Each model has an explicit `__repr__`; `Connection.__repr__` leaves out `encrypted_token`.
- **Migration `0002`**: generated with the exact autogenerate command and kept almost as generated. I only replaced the "auto generated" comments. The Ruff hook kept the `op` / `sa` imports. Alembic applies the metadata's naming convention to the CHECK constraints the `sa.Enum` columns create, so the database names are `ck_connections_provider`, `ck_accounts_owner_tag` and so on. I checked them in `pg_constraint`.
- **Composite unique name**: the `uq` convention in `base.py` uses only the first column, so `(connection_id, provider_account_id)` is named `uq_accounts_connection_id`. I kept the convention's name because the criterion asks for it, and `base.py` is outside this task's files. Task 9's upsert can target it by that name or by its columns.
- **Tests**: `tests/unit/test_models.py` covers columns, types, defaults, FKs, enum values, convention names and `repr`. `tests/integration/test_models_db.py` has one test per scenario in the list. `tests/integration/conftest.py` gains:
  - `migrated_engine` (session scope): runs `alembic upgrade head`, then asserts `select count(*) from users` is unchanged at the end of the run.
  - `db_session`: an outer transaction that is rolled back after each test, with `join_transaction_mode="create_savepoint"`. Statements expected to fail run inside `session.begin_nested()`.
- **Changed test**: `tests/unit/test_database.py::test_base_metadata_has_naming_convention_and_no_tables` asserted that `Base.metadata` has no tables. That is no longer true, so it is now `..._and_model_tables` and asserts the three tables.
- **Verified locally** (2026-11-14):
  - `make test` with `.env` exported: 69 passed, the 17 new integration tests included. `users` count was 0 before and 0 after.
  - With `DATABASE_URL` unset, `make test` gave 45 passed and 24 skipped with a reason. `make lint` is clean.
  - On a scratch database (created and then dropped): `upgrade head` → `current` prints `0002 (head)` → `downgrade 0001` leaves only `alembic_version`, no enum types, `vector` kept → `upgrade head` → `check` reports no changes. The CI sequence (upgrade, downgrade base, upgrade, check) also passed.
  - On the dev DB at `0001`, `make migrate` moved it to `0002`.
- **Stale image gotcha**: `make migrate` runs `docker compose run --rm api`, which uses the existing image. The image copies `migrations/` at build time, so with an image built before this task, `make migrate` exits 0 but stays at `0001`. Run `docker compose build api` (or `make run`, which builds) first. I left the Makefile alone because it's outside this task's files. A `--build` flag there may be worth a follow-up.
- **Not done by me**: the CI run for the pushed commit. That needs the human push.

## QA verdict

(QA adds its PASS or FAIL verdict here.)
