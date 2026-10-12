# 1. Set up an empty project with a passing test and CI

Depends on: 0

## Goal

A fresh clone installs with `uv sync`, and `make lint` and `make test` both pass, locally and in a GitHub Actions workflow that runs on every push and pull request. The repository has the folder layout from `_docs/plan.md` § 5 Repository layout, with no application code yet.

## Acceptance criteria

### Project and dependencies

- [ ] `pyproject.toml` defines a package named `budgeter`, uses the `src/` layout (`src/budgeter/`), and is managed by uv
- [ ] Python version is pinned to 3.13: `requires-python = ">=3.13"` in `pyproject.toml` and a `.python-version` file containing `3.13`
- [ ] The package has no runtime dependencies; `pytest` and `ruff` are the only dependencies, both in a uv dev dependency group
- [ ] `uv.lock` is committed, and `uv sync --locked` succeeds on a fresh clone
- [ ] After `uv sync`, `uv run python -c "import budgeter"` succeeds from the repository root

### Folder layout

- [ ] These packages exist, each with an empty `__init__.py`: `src/budgeter/`, `core/`, `ingestion/`, `api/`, `mcp_server/`, `agent/`, `scheduler/`, `ui/` (all under `src/budgeter/`)
- [ ] These folders exist and are tracked in git with a `.gitkeep`: `scripts/`, `evals/`, `tests/integration/`
- [ ] `tests/unit/` exists and contains the trivial test
- [ ] No other source files are added (no `docker-compose.yml`, `.env.example`, Dockerfiles, Alembic config or FastAPI code)

### Tooling configuration

- [ ] Ruff is configured in `pyproject.toml` (`[tool.ruff]`) with `target-version = "py313"`, `line-length = 100`, and lint rules `E`, `F`, `I`, `UP` and `B` selected
- [ ] pytest is configured in `pyproject.toml` (`[tool.pytest.ini_options]`) with `testpaths = ["tests"]`
- [ ] Exactly one trivial test exists at `tests/unit/test_smoke.py`; it imports `budgeter` and passes

### Makefile

- [ ] `make test` runs pytest through uv and exits 0, reporting 1 passed
- [ ] `make lint` runs both `ruff check` and `ruff format --check` through uv and exits 0
- [ ] `make lint` exits non-zero when a lint error is introduced (e.g. an unused import), and when a file is badly formatted
- [ ] `make test` exits non-zero when the test is changed to fail

### Git hygiene

- [ ] `.gitignore` keeps its existing entries (`.env`, `old versions/`) and adds at least `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `dist/`, `build/` and `*.egg-info/`
- [ ] `git status` is clean after running `uv sync`, `make lint` and `make test` (no generated files show up as untracked)
- [ ] No secrets, tokens, `.env` files or financial data are committed

### CI

- [ ] `.github/workflows/ci.yml` runs on `push` (all branches) and `pull_request`
- [ ] The workflow installs uv with `astral-sh/setup-uv`, installs Python 3.13, runs `uv sync --locked`, then runs `make lint` and `make test`
- [ ] No step uses `continue-on-error`, so a lint error or a failing test fails the workflow
- [ ] After the human pushes the commit, the workflow run on GitHub for that commit is green

### README

- [ ] `README.md` exists with the project name, a one-sentence description (taken from `_docs/plan.md`), a link to `_docs/plan.md`, and the commands `uv sync`, `make lint` and `make test`
- [ ] The README shows the CI status badge for the workflow: `https://github.com/jubinjacob93/budgeter-dev/actions/workflows/ci.yml/badge.svg`, linking to the workflow's Actions page

## Out of scope

- `make run`, `docker-compose.yml`, Dockerfiles and `.env.example` - task 2
- `make migrate`, Alembic setup and the CI step that runs migrations on a fresh Postgres - task 3
- `make seed` and the seed script - task 6
- Integration tests against Postgres - task 2 onwards (`tests/integration/` is only created here)
- Running the eval suite in CI - task 39
- Nested folders inside the packages (`ingestion/providers/`, `api/routers/`, `api/schemas/`, `mcp_server/tools/`, `ui/pages/`) - created by the tasks that first put code in them (8, 2, 31, 18)
- The full README with features, architecture, demo-mode quickstart and screenshots - task 54
- Any runtime dependency (FastAPI, SQLAlchemy, Streamlit, etc.) - added by the task that first needs it
- migrations/ folder - created by alembic init in task 3

## Constraints

- Files this task may create or change: `pyproject.toml`, `uv.lock`, `.python-version`, `Makefile`, `.gitignore`, `README.md`, `.github/workflows/ci.yml`, `src/budgeter/**/__init__.py`, `tests/unit/test_smoke.py`, and the `.gitkeep` files listed above. Do not touch `_docs/` except to add implementation notes to this file.
- Use uv (`uv init --package` or equivalent) and its default build backend; no setuptools, Poetry, pip or `requirements.txt`.
- The human approves `pytest` and `ruff` as dev dependencies by approving this groomed task (AGENTS.md: no dependencies without asking). Do not add any other dependency, including pytest plugins.
- Makefile recipes call tools through `uv run`, so they never depend on an activated virtualenv.
- Pin GitHub Actions to a major version tag (e.g. `actions/checkout@v4`, `astral-sh/setup-uv@v6` or the current major); no secrets are needed in this workflow.
- `.gitattributes` already forces LF line endings; keep it. The Makefile must use tab-indented recipes.
- Follow `_docs/plan.md` § 5 (Repository layout, Code conventions, Library defaults: uv, Ruff) and § 9 (Testing and CI).
- Commit with messages that start with `task 01:` (e.g. `task 01: add pyproject and Makefile`). Do not push; the human pushes and checks the CI run.

## QA verdict

(QA adds its PASS or FAIL verdict here.)
