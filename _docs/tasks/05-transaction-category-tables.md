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

## QA verdict

(QA adds its PASS or FAIL verdict here.)
