# 5. Create the transaction and category tables

Depends on: 4

## Goal

`raw_transactions`, `transactions`, `transaction_splits`, `merchants`, `categories` and `category_rules` exist as SQLAlchemy 2.0 models in `src/budgeter/core/models/` and as Alembic migration `0003`. A transaction belongs to exactly one account and can point to a merchant and a category. The database rejects a second transaction or raw payload with the same `(provider, provider_txn_id)`, as well as orphaned rows, duplicate merchant, category and rule names, and unknown provider values. Integration tests insert sample rows and read them back without leaving data in the development database. The pgvector `embedding` column on `merchants` is not part of this task. It moves to task 28, which knows the vector size once task 27 has chosen the embedding model.

## Acceptance criteria

### Decisions this task records

- [ ] **Amount sign:** `transactions.amount` and `transaction_splits.amount` are signed `NUMERIC(14, 2)`. Splits use the same sign as the parent transaction. Negative means money leaves the account (purchases, fees, payments out) and positive means money comes in (income, refunds, transfers in). Every provider (tasks 8, 10, 11, 22, 23) converts to this convention, and spending queries (tasks 14, 15, 19) rely on it
- [ ] **Deduplication key:** `transactions` stores its own `provider` and `provider_txn_id` columns, and `(provider, provider_txn_id)` is unique, as plan § 6 says. `provider` uses the existing `Provider` enum. The ingestion pipeline (task 9) copies `provider` from the account's connection. `raw_transactions` is unique on the same pair, so re-importing the same payload updates it instead of adding a row (task 9 decides how)
- [ ] `_docs/plan.md` § 6 is updated: the rows for `raw_transactions`, `transactions`, `transaction_splits`, `merchants`, `categories` and `category_rules` list the columns this task adds (see below), the `transactions` note states the sign convention, and the `merchants` row says the `embedding` column is added in task 28

### Models (`src/budgeter/core/models/`)

- [ ] Models use SQLAlchemy 2.0 style (`Mapped[...]`, `mapped_column`) on the existing `Base`, with one module per table: `raw_transaction.py`, `transaction.py`, `transaction_split.py`, `merchant.py`, `category.py`, `category_rule.py`. `models/__init__.py` also re-exports `RawTransaction`, `Transaction`, `TransactionSplit`, `Merchant`, `Category` and `CategoryRule`, so Alembic sees all six tables
- [ ] The `provider` columns use the existing `enums.string_enum(Provider, "provider")` helper: a `VARCHAR` with a named CHECK constraint and no native Postgres `ENUM`
- [ ] Relationships, each with `back_populates` and no ORM cascade deletes:
  - `Account.transactions` ↔ `Transaction.account`
  - `Transaction.splits` ↔ `TransactionSplit.transaction`
  - `Merchant.transactions` ↔ `Transaction.merchant`
  - `Category.transactions` ↔ `Transaction.category`
  - `Category.rules` ↔ `CategoryRule.category`
  - `TransactionSplit.category`, one-way
- [ ] Every model has an explicit `__repr__` that does not include `raw_transactions.payload` or `transactions.notes`. A unit test checks both

### `raw_transactions`

- [ ] Columns:
  - `id`: integer identity primary key
  - `connection_id`: FK to `connections.id`, `NOT NULL`, `ON DELETE RESTRICT`, indexed. Records which login the payload came from, so a sync can be replayed
  - `provider`: `Provider`, `NOT NULL`
  - `provider_txn_id`: `VARCHAR(255)`, `NOT NULL`
  - `payload`: `JSONB`, `NOT NULL`
  - `fetched_at`: `timestamptz`, `NOT NULL`, server default `now()`
- [ ] `(provider, provider_txn_id)` is unique. The same `provider_txn_id` under a different provider is allowed
- [ ] A nested payload (dicts, lists, `null`, unicode, a numeric string such as `"12.30"`) reads back equal to what was inserted

### `transactions`

- [ ] Columns:
  - `id`: integer identity primary key
  - `account_id`: FK to `accounts.id`, `NOT NULL`, `ON DELETE RESTRICT`, indexed
  - `provider`: `Provider`, `NOT NULL`
  - `provider_txn_id`: `VARCHAR(255)`, `NOT NULL`
  - `date`: `DATE`, `NOT NULL`, indexed
  - `amount`: `NUMERIC(14, 2)`, `NOT NULL`
  - `merchant_raw`: `VARCHAR(500)`, `NOT NULL`. The provider's description as received
  - `merchant_id`: FK to `merchants.id`, nullable, `ON DELETE RESTRICT`, indexed
  - `category_id`: FK to `categories.id`, nullable, `ON DELETE RESTRICT`, indexed
  - `is_transfer`: `BOOLEAN`, `NOT NULL`, server default `false`
  - `notes`: `TEXT`, nullable
  - `created_at`: `timestamptz`, `NOT NULL`, server default `now()`
- [ ] `(provider, provider_txn_id)` is unique. A second row with the same pair raises `IntegrityError`, even on a different account. The same `provider_txn_id` under a different provider succeeds
- [ ] A transaction with no merchant and no category (`merchant_id` and `category_id` `NULL`) can be saved. It counts as uncategorized
- [ ] `amount` is never a float: `Decimal("-42.10")`, `Decimal("1500.00")` and `Decimal("0.00")` read back exactly. Zero is allowed, because some providers report $0 authorizations
- [ ] Inserting a transaction without `is_transfer` gives `false`

### `transaction_splits`

- [ ] Columns:
  - `id`: integer identity primary key
  - `transaction_id`: FK to `transactions.id`, `NOT NULL`, `ON DELETE RESTRICT`, indexed
  - `category_id`: FK to `categories.id`, `NOT NULL`, `ON DELETE RESTRICT`, indexed
  - `amount`: `NUMERIC(14, 2)`, `NOT NULL`
- [ ] A transaction can have several splits, including two with the same category. This task does not check that the splits add up to the parent amount (see Out of scope)

### `merchants`

- [ ] Columns:
  - `id`: integer identity primary key
  - `normalized_name`: `VARCHAR(255)`, `NOT NULL`, unique
  - `created_at`: `timestamptz`, `NOT NULL`, server default `now()`
- [ ] No `embedding` or other vector column exists, and the `pgvector` Python package is not added
- [ ] A second merchant with the same `normalized_name` raises `IntegrityError`. Names differing only in case (`Blue Bottle` and `blue bottle`) are both allowed, because producing one consistent spelling is the normalizer's job (task 12)

### `categories`

- [ ] Columns:
  - `id`: integer identity primary key
  - `name`: `VARCHAR(100)`, `NOT NULL`, unique
  - `group_name`: `VARCHAR(100)`, `NOT NULL`
  - `created_at`: `timestamptz`, `NOT NULL`, server default `now()`
- [ ] The plan's `group` field is named `group_name`, because `GROUP` is a reserved word in SQL. Plan § 6 uses the new name
- [ ] A duplicate `name` raises `IntegrityError`. Several categories can share a `group_name`

### `category_rules`

- [ ] Columns:
  - `id`: integer identity primary key
  - `pattern`: `VARCHAR(255)`, `NOT NULL`, unique
  - `category_id`: FK to `categories.id`, `NOT NULL`, `ON DELETE RESTRICT`, indexed
  - `created_at`: `timestamptz`, `NOT NULL`, server default `now()`
- [ ] A duplicate `pattern` raises `IntegrityError`, so one pattern cannot point to two categories. Several patterns can point to the same category

### Constraint names

- [ ] Every primary key, foreign key, unique constraint, check constraint and index in migration `0003` has an explicit name that follows the convention in `core/models/base.py`. Because the `uq` convention uses only the first column, the composite keys are named `uq_transactions_provider` and `uq_raw_transactions_provider`. The task 9 upsert targets them by these names or by their columns. A unit test inspects `Base.metadata` and finds no constraint or index with a `None` name on any of the nine tables

### Migration `0003`

- [ ] The file is `migrations/versions/0003_create_transaction_category_tables.py`, with revision `0003` and `down_revision = "0002"`. It is created with `uv run alembic revision --autogenerate -m "create transaction category tables" --rev-id 0003` and then reviewed by hand. If the Ruff hook stripped the `op` / `sa` imports, restore them
- [ ] Upgrade creates the six tables with the columns, defaults and constraints above, after the tables they reference (`categories` and `merchants` before `transactions`, `transactions` before `transaction_splits`). Downgrade drops them in reverse order and leaves `users`, `connections`, `accounts` and the `vector` extension in place
- [ ] On a fresh database, each of these exits 0, in order: `alembic upgrade head`; `alembic current`, which prints `0003 (head)`; `alembic downgrade 0002`, which leaves none of the six tables; `alembic upgrade head` again; `alembic check`
- [ ] On a database already at `0002` (the existing dev database, with rows in `users`, `connections` and `accounts`), `make migrate` exits 0, moves it to `0003` and leaves the existing rows unchanged. Rebuild the image first (`docker compose build api`); see the stale-image note in task 4
- [ ] The existing CI `Migrate` step (upgrade, downgrade base, upgrade, check) passes unchanged

### Tests

- [ ] Unit tests (no database) check that the six tables are in `Base.metadata` with the columns, types, nullability and server defaults above, that `merchants` has no `embedding` column, that constraint and index names follow the convention, and that `__repr__` leaves out `payload` and `notes`. `tests/unit/test_database.py`'s table-list assertion is updated to the nine tables
- [ ] Integration tests reuse the existing `tests/integration/conftest.py` fixtures (`migrated_engine`, plus a `db_session` that rolls back after each test with `create_savepoint`). Statements expected to fail run inside `session.begin_nested()`. The session-end check in `migrated_engine` is extended so that `transactions`, `raw_transactions`, `merchants`, `categories` and `category_rules` row counts are the same before and after the run
- [ ] Integration tests cover, each as its own test:
  - one category, one merchant, one rule and one transaction with two splits, inserted through the ORM and read back in a new query (including through every relationship above) with all fields equal
  - **the unique constraint:** a second transaction with the same `(provider, provider_txn_id)` raises `IntegrityError`, both on the same account and on another account. A second transaction with the same `provider_txn_id` and a different `provider` succeeds
  - the same three cases for `raw_transactions`
  - a nested JSON payload round-trips exactly
  - signed amounts `Decimal("-42.10")`, `Decimal("1500.00")` and `Decimal("0.00")` round-trip exactly, and `is_transfer` defaults to `false` when the database fills it
  - a transaction with `merchant_id` and `category_id` `NULL` saves and reads back
  - an unknown `provider` value inserted with raw SQL raises `IntegrityError` on `transactions` and on `raw_transactions`
  - a foreign key to a missing row raises `IntegrityError`, one case each for: `transactions.account_id`, `transactions.merchant_id`, `transactions.category_id`, `transaction_splits.transaction_id`, `transaction_splits.category_id`, `category_rules.category_id` and `raw_transactions.connection_id`
  - raw-SQL `DELETE`s that must be blocked by `RESTRICT`, each raising `IntegrityError`: an account with transactions, a merchant with transactions, a category used by a transaction, a split or a rule, a transaction with splits, and a connection with raw transactions
  - a duplicate merchant `normalized_name`, category `name` and rule `pattern` each raise `IntegrityError`. Names differing only in case are both accepted for merchants
- [ ] On a fresh clone without a database, `make test` and `make lint` exit 0, with the integration tests skipped and a reason shown. With the stack running, `make migrate` run and `.env` exported, `make test` passes and runs the integration tests
- [ ] The CI run for the pushed commit is green and shows the new integration tests passing, not skipped

## Out of scope

- The `embedding` vector column on `merchants`, its index, the `pgvector` Python package and the vector size. Moved to task 28, which adds them with a migration once task 27 has chosen the embedding model
- Checking that splits add up to the parent amount, and how budgets and charts use splits. Task 49
- Normalizing merchant names, linking transactions to merchants, and how merchants differing only in case are merged. Task 12
- The starting category list, how rules match (match field, match type, priority) and a column recording whether a category came from a rule, the LLM or a person, so rules are never overridden. Task 13 adds these with a migration
- Setting `is_transfer` and pairing the two sides of a transfer. Task 14
- Marking refunds and linking a refund to its original purchase. Task 15
- Upserting raw and normalized rows, storing raw payloads before normalizing, and how a changed payload for the same ID is handled. Task 9
- Making sure CSV and Monarch imports produce a stable, unique `provider_txn_id`. Tasks 10 and 11
- The same real-world transaction arriving from two providers (for example Monarch history overlapping the first Plaid sync). Task 22, and task 23 for SimpleFIN
- Pending vs. posted transactions and Plaid's removed transactions. Task 22
- Checking that `transactions.provider` matches the provider of the account's connection. Task 9 sets it, and the database does not enforce it
- `review_queue`, `budgets`, holdings and `recurring_series`. Tasks 30, 19, 9 and 50
- Seed data. Tasks 6 and 7
- API endpoints and schemas for these tables. Tasks 13, 17, 30 and 49
- Read access for the MCP server's database role. Task 31

## Constraints

- Only create or change these files:
  - in `src/budgeter/core/models/`: `__init__.py`, `account.py` (only the `transactions` relationship), and the six new modules listed above
  - `migrations/versions/0003_create_transaction_category_tables.py`
  - tests under `tests/unit/` and `tests/integration/`, including `conftest.py` and the table-list assertion in `tests/unit/test_database.py`
  - `_docs/plan.md` § 6, only the six table rows
  - this task file, only to add implementation notes
- Do not change other `_docs/` files. Do not change `core/models/base.py` or `enums.py` (reuse `Provider` and `string_enum` as they are) or the Makefile.
- No new dependencies (AGENTS.md). In particular, do not add `pgvector`, pytest plugins or factory libraries. `JSONB` comes from `sqlalchemy.dialects.postgresql`.
- Use SQLAlchemy 2.0 style only (`DeclarativeBase`, `Mapped`, `mapped_column`, `select()`), with no legacy `Query` API. The engine stays synchronous.
- Every schema change goes through migration `0003`. Do not call `Base.metadata.create_all()` anywhere, including tests. Do not edit `0001` or `0002`.
- Money is `NUMERIC` / `Decimal`, never `float`, and follows the sign convention above.
- No secrets or real data in git: no real merchant histories, account data or bank payloads in tests or migrations. Fixtures are made up (for example `"SQ *TEST CAFE #001"`, `{"fake": true}`).
- The MCP server and agent stay read-only (AGENTS.md). Nothing in this task grants any role access.
- Follow `_docs/plan.md` § 5 (Repository layout: shared models in `core/`; Code conventions), § 6 (data model) and § 7 (Rules for all providers: dedupe on the provider's transaction ID, store raw payloads). Follow the task 4 patterns in `core/models/` and `tests/integration/conftest.py`.
- Commit with messages that start with `task 05:`. Do not push; the human pushes and checks the CI run.

## Implementation notes

- **Models**: six new modules in `src/budgeter/core/models/`, following the task 4 patterns: `Identity()` PKs, `string_enum(Provider, "provider")`, RESTRICT and indexed FKs, timestamptz `server_default=now()`. `Account.transactions` is added, and `__init__.py` re-exports all six. `transaction.py` uses `import datetime as dt` so the `date` column doesn't shadow the `date` type. `RawTransaction` has no ORM relationship to `Connection`, because none was asked for; it only has the `connection_id` FK. `payload` is `Mapped[Any]` with explicit `nullable=False`. Because JSONB's `none_as_null` is off, a Python `None` payload is stored as JSON `null`, not SQL NULL. `is_transfer` uses `server_default=false()`.
- **`__repr__`**: `RawTransaction` leaves out `payload` and `Transaction` leaves out `notes`. `Transaction`'s repr does include `amount` and `date`.
- **Migration `0003`**: autogenerated with the command in the task. Ruff kept the `op` / `sa` / `postgresql` imports. The only hand edits replaced the autogenerate marker comments. Table order: categories → merchants → category_rules → raw_transactions → transactions → transaction_splits. Downgrade drops them in reverse.
- **Migration checks run**:
  - On a scratch database `budgeter_t05_scratch`, since dropped: `upgrade head` → `current` = `0003 (head)` → `downgrade 0002` (only users/connections/accounts left, `vector` still there) → `upgrade head` → `check` ("No new upgrade operations detected"). Then the CI sequence (`downgrade base` / `upgrade head` / `check`).
  - On the dev DB, after `docker compose build api`: it had no rows in users/connections/accounts. To check the "existing rows unchanged" criterion, I downgraded it to `0002`, inserted one made-up user/connection/account, and ran `make migrate`. Counts and an md5 of the three tables' rows were identical before and after. I then deleted the made-up rows, so the dev DB is at `0003` with no rows, as before.
- **Tests**:
  - `tests/unit/test_models.py` now covers all nine tables: columns, types, nullability, server defaults, sizes, FKs, uniques, convention names, relationships, no `embedding`, and reprs.
  - `tests/unit/test_database.py` lists nine tables.
  - `tests/integration/conftest.py` now checks row counts for users, transactions, raw_transactions, merchants, categories and category_rules before and after the session.
  - New `tests/integration/test_transactions_db.py` has one test (or parametrized set) per criterion bullet, plus split-amount round-trip and same-category splits.
  - Results: `make test` with `.env` exported gives 158 passed. With `DATABASE_URL` unset it gives 101 passed, 57 skipped with the reason shown. `make lint` is clean.
- **For the reviewer**:
  - `test_deleting_connection_with_raw_transactions_is_restricted` deletes the account first, so only the raw transaction holds the connection.
  - Under the installed SQLAlchemy, assigning `rule.category = category` does not cascade the rule into the session through the backref, so tests `session.add()` new objects explicitly.
  - CI has not run yet; the human pushes.

## QA verdict: PASS

Tested `task-05` at `b260821` (same as `origin/task-05`) in a fresh clone, with Docker in Compose project `budgeterqa` (ports 5433/8001). The developer's stack, `budgeter-dev_db-data` and the dev DB were not touched.

### Decisions this task records
- [x] Amount sign: both `amount` columns are `numeric(14,2)` in the live DB, and the convention is documented on `Transaction` and in plan § 6 - PASS
- [x] Deduplication key: `provider` (`Provider`, CHECK) and `provider_txn_id` are on `transactions`, and `uq_transactions_provider` / `uq_raw_transactions_provider` are `UNIQUE (provider, provider_txn_id)` in the live DB - PASS
- [x] Plan § 6: only the six rows changed. They list the new columns, the sign convention, `group_name`, and the `embedding` column moving to task 28 - PASS

### Models
- [x] One module per table, 2.0 style, all six re-exported from `models/__init__.py` - PASS
- [x] `provider` uses `string_enum`. In the DB it is VARCHAR(9) with `ck_transactions_provider` / `ck_raw_transactions_provider`, and `pg_type` has no enum types - PASS
- [x] All six relationships use `back_populates` (`TransactionSplit.category` is one-way), with no cascade. `account.py` changed only for `transactions` - PASS
- [x] Explicit `__repr__` on every model. `payload` and `notes` are left out, and unit tests check both - PASS

### Tables (checked against `information_schema` / `pg_constraint` / `pg_indexes` after the migration)
- [x] `raw_transactions`: columns, types, NOT NULL and `now()` default match. The FK to connections is RESTRICT and indexed. Unique on the pair, and a different provider is allowed. A nested payload round-trips (integration test) - PASS
- [x] `transactions`: all 12 columns match (VARCHAR 255/500, DATE, NUMERIC(14,2), nullable merchant/category, `is_transfer` default `false`, nullable `notes`, timestamptz `now()`). The three FKs are RESTRICT and indexed, and `date` is indexed. Unique, NULL merchant/category, Decimal round-trip and `is_transfer` default are covered by passing tests - PASS
- [x] `transaction_splits`: columns and RESTRICT FKs are indexed. Several splits, including two with the same category, are allowed - PASS
- [x] `merchants`: `normalized_name` VARCHAR(255) is unique and case-sensitive. There is no `embedding` column, and `pgvector` is in neither `pyproject.toml` nor `uv.lock` - PASS
- [x] `categories`: `name` is unique, `group_name` is not unique, and plan § 6 uses `group_name` - PASS
- [x] `category_rules`: `pattern` is unique, the FK is RESTRICT and indexed, and several patterns per category are allowed - PASS

### Constraint names
- [x] Every PK/FK/UQ/CK/index in the live DB follows the convention, including `uq_transactions_provider` and `uq_raw_transactions_provider`. `test_every_constraint_and_index_has_a_convention_name` covers all nine tables - PASS

### Migration `0003`
- [x] File name, `revision = "0003"`, `down_revision = "0002"` - PASS
- [x] Create order is categories → merchants → category_rules → raw_transactions → transactions → transaction_splits, and downgrade reverses it - PASS
- [x] Fresh DB (`budgeter_qa_fresh`): `upgrade head` 0, `current` = `0003 (head)` 0, `downgrade 0002` 0 (left `accounts, alembic_version, connections, users`; `vector` still installed), `upgrade head` 0, `check` 0 ("No new upgrade operations detected") - PASS
- [x] Existing DB at `0002`: I built the api image from `main` (`224818a`, migrations up to 0002) and migrated to `0002 (head)`. Then I inserted 2 made-up users, 2 connections and 3 accounts and saved per-table count + md5 of all rows. I checked out `task-05`, ran `docker compose -p budgeterqa build api` and `COMPOSE_PROJECT_NAME=budgeterqa make migrate`: exit 0, "Running upgrade 0002 -> 0003", `current` = `0003 (head)`. Counts and md5s were identical before and after (users 2, connections 2, accounts 3) - PASS
- [x] CI `Migrate` sequence (`downgrade base`, `upgrade head`, `check`) passes locally, and the `Migrate` step is green in CI - PASS

### Tests
- [x] Unit tests cover the nine tables' columns, types, nullability, defaults, the missing `embedding`, convention names and reprs. `test_database.py` lists nine tables - PASS
- [x] Integration tests use `migrated_engine` / `db_session` (`create_savepoint`) and `begin_nested()` for failures. The session-end check now counts `users`, `transactions`, `raw_transactions`, `merchants`, `categories` and `category_rules` - PASS
- [x] Each listed integration case is its own test or parametrized set in `test_transactions_db.py` (33 tests, all pass) - PASS
- [x] Fresh clone without a DB: `make lint` exit 0, and `make test` exit 0 with 101 passed, 57 skipped ("DATABASE_URL is not set; start the stack and export DATABASE_URL from .env"). With the QA stack running, migrated and `.env` exported: `make test` exit 0, 158 passed. Every row count was 0 afterwards - PASS
- [x] CI for `b260821` is green (push run 45759571038, PR run 45759615032). The Test step shows 158 passed and none skipped, so the integration tests ran - PASS

Tests: `make test` (no DB) 101 passed, 57 skipped. `make test` (QA stack, empty migrated DB) 158 passed, 0 failed. `make lint` clean.

Secrets: the task-05 diff has no keys, tokens, passwords or real-looking bank data. Fixtures are made up (`t05@example.com`, `SQ *TEST CAFE #001`, `{"fake": true}`). No `.env`, `.pem` or `.key` files are tracked.

### Observations (not blocking; no criterion fails)
- **Task-04 test assumes an empty `accounts` table.** I ran `make test` against the QA DB while it still held my made-up 0002 rows. `tests/integration/test_models_db.py::test_query_by_owner_tag_across_two_users` failed: `['a-mine', 'b-mine', 'qa-acc-1'] != ['a-mine', 'b-mine']`. The test filters only by `owner_tag`, so any existing `mine` account breaks it. Task 05 did not change this file, and it passes on an empty DB. It will fail on a dev DB that holds data, for example after task 6 seeds one.
- The `migrated_engine` leftover check doesn't count `transaction_splits`, `accounts` or `connections`. The criterion doesn't ask for them. A leftover split would need a leftover transaction, which is counted.
- The "downgrade leaves `vector` and the task-4 tables" behaviour is checked by hand here, not by an automated test.

### Cleanup
- `docker compose -p budgeterqa down -v --rmi local` (run from the clone) removed container `budgeterqa-db-1`, volume `budgeterqa_db-data` (this held the made-up 0002 rows and the `budgeter_qa_fresh` database) and network `budgeterqa_default`
- `--rmi local` left `budgeterqa-api:latest` in place, so I removed it by exact name with `docker image rm budgeterqa-api:latest`
- Deleted the scratch clone `/tmp/claude-1000/-home-vjubin-projects-budgeter-dev/f4adc3fc-6a5c-46c2-81ca-9ada19cbcde8/scratchpad/qa-task05` (origin `jubinjacob93/budgeter-dev`, branch `task-05`) and QA's snapshot files
- Not touched: `budgeter-dev-api-1`, `budgeter-dev-db-1`, volume `budgeter-dev_db-data`, image `budgeter-dev-api`
