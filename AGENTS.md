# AGENTS.md

Self-hosted personal finance app for one household: transactions, budgets, net worth and a read-only AI agent. The full plan is in `_docs/plan.md`.

## Commands

- `uv sync` - install dependencies
- `make run` - start the full stack with Docker Compose
- `make test` - run the whole test suite
- `uv run pytest tests/path/to/test_file.py` - run one test file
- `make lint` - run Ruff
- `make migrate` - apply Alembic migrations
- `make seed` - load synthetic seed data

## Rules

- Follow the repository layout and code conventions in `_docs/plan.md`.
- Add dependencies only in `pyproject.toml`, and never without asking first.
- Every schema change goes through an Alembic migration.
- All configuration comes from environment variables. Never commit `.env`, secrets, API keys, provider tokens, real financial data or personal documents.
- The MCP server and the agent are read-only. Never give them write access to the database.
- Request only read products from bank providers (Transactions, Balance, Investments).
- The Streamlit UI talks to the backend only through `src/budgeter/ui/api_client.py`.
- The agent never does arithmetic itself; numbers come from tools.
- Commit regularly, referencing the task number.

## Documents

- `_docs/process.md` - how work is organized; read at the start of every task
- `_docs/plan.md` - scope, architecture and decisions
- `_docs/tasks.md` - the backlog
- `_docs/task-template.md` - the format for a groomed task
- `_docs/team/pm.md` - read when grooming a task
- `_docs/team/software-engineer.md` - read when implementing a task
- `_docs/team/qa-engineer.md` - read when testing a task
