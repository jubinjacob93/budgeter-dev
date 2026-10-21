.PHONY: run lint test

run:
	docker compose up --build

lint:
	uv run ruff check .
	uv run ruff format --check .

test:
	uv run pytest
