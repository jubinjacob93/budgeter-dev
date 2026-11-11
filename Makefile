.PHONY: run lint test migrate

run:
	docker compose up --build

# Runs in a one-off api container, so it uses the DATABASE_URL Compose gives api (host db).
migrate:
	docker compose run --rm api alembic upgrade head

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest
