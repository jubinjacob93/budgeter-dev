FROM python:3.13-slim AS api

COPY --from=ghcr.io/astral-sh/uv:0.13.0 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first so this layer is cached until uv.lock changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
RUN uv sync --locked --no-dev --no-editable

RUN useradd --system --no-create-home --uid 10001 app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
CMD ["uvicorn", "budgeter.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
