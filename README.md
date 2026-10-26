# Budgeter

[![CI](https://github.com/jubinjacob93/budgeter-dev/actions/workflows/ci.yml/badge.svg)](https://github.com/jubinjacob93/budgeter-dev/actions/workflows/ci.yml)

A self-hosted, AI-assisted personal finance app for a single household: transactions, budgets, net worth and a chat agent that answers questions about your money.

See [`_docs/plan.md`](_docs/plan.md) for the full plan.

## Development

```sh
uv sync      # install dependencies
make lint    # run Ruff (lint and format check)
make test    # run the test suite
```

### Running the stack

```sh
cp .env.example .env   # then set POSTGRES_PASSWORD (and DATABASE_URL to match)
make run               # build and start Postgres (with pgvector) and the API
```

The API is at <http://localhost:8000/health> by default (`API_PORT` in `.env`), and its OpenAPI docs are at <http://localhost:8000/docs>. Both services listen on `127.0.0.1` only.

### Integration tests

Integration tests (marked `integration`) need a real Postgres. Without `DATABASE_URL` they are skipped. To run them locally, start the stack and export the variables from `.env` in the same shell:

```sh
set -a && . ./.env && set +a
make test
```

If `DATABASE_URL` is set but the database is not reachable, the integration tests fail instead of being skipped.
