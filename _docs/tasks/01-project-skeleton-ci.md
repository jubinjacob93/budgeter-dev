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

## Implementation notes

- Scaffolded from `uv init --package` (uv 0.13.0), keeping its `uv_build` backend. Removed the generated `main()` and `[project.scripts]` entry so every `__init__.py` is empty, and left out the `authors` field.
- Dev group: `pytest>=8.4`, `ruff>=0.13`. The lock resolves to pytest 9.1.1 and ruff 0.17.1.
- `make lint` runs `ruff check .` and then `ruff format --check .`. I checked that it exits 2 for an unused import and for a formatting-only error (which `ruff check` alone lets through). `make test` exits 2 when the test is made to fail.
- CI installs Python with `uv python install 3.13`, which follows `.python-version`. Actions are pinned to `actions/checkout@v5` and `astral-sh/setup-uv@v6`.
- Verified on a fresh `git clone`: `uv sync --locked`, `make lint`, `make test` and `import budgeter` all succeed, and `git status` stays clean.
- For the reviewer: Ruff 0.17 also format-checks Python code blocks inside Markdown files (it reports 20 files: 10 `.py`, `pyproject.toml` and the `.md` files in the repo root and `_docs/`). They all pass today. A badly formatted Python snippet in a doc would now fail `make lint`.
- Not verified: the green CI run on GitHub. The human needs to push first.

## QA verdict: PASS

All checks ran on a fresh `git clone` of `65e94fb` (uv 0.13.0, CPython 3.13.16). Negative checks were made in that clone only and then reverted.

### Project and dependencies

- [x] `pyproject.toml` defines package `budgeter` with the `src/` layout, managed by uv (`uv_build` backend) - PASS
- [x] `requires-python = ">=3.13"`, and `.python-version` contains `3.13` - PASS
- [x] `dependencies = []`; the `dev` group holds only `pytest` and `ruff`. `uv tree --no-dev` shows only `budgeter` - PASS
- [x] `uv.lock` is tracked; `uv sync --locked` exits 0 on the fresh clone - PASS
- [x] `uv run python -c "import budgeter"` exits 0 and resolves to `src/budgeter/__init__.py` - PASS

### Folder layout

- [x] All 8 packages exist with `__init__.py`; `find src -name __init__.py -size +0` finds none, so all are empty - PASS
- [x] `scripts/.gitkeep`, `evals/.gitkeep` and `tests/integration/.gitkeep` are tracked - PASS
- [x] `tests/unit/test_smoke.py` exists - PASS
- [x] `git ls-files` shows no other source files (no compose, Dockerfiles, `.env.example`, Alembic, FastAPI code) - PASS

### Tooling configuration

- [x] `[tool.ruff]` sets `target-version = "py313"` and `line-length = 100`; `[tool.ruff.lint]` selects `E`, `F`, `I`, `UP`, `B` - PASS
- [x] `[tool.pytest.ini_options]` sets `testpaths = ["tests"]` - PASS
- [x] Exactly one test, `test_package_imports`, imports `budgeter` and passes - PASS

### Makefile

- [x] `make test` runs `uv run pytest`, exits 0, reports `1 passed` - PASS
- [x] `make lint` runs `uv run ruff check .` and `uv run ruff format --check .`, exits 0 - PASS
- [x] With `import os` added to a new module, `make lint` exits 2. With `x  =  1` (formatting only; `ruff check` alone exits 0), `make lint` exits 2 - PASS
- [x] With the assertion changed to `== "nope"`, `make test` exits 2 - PASS
- [x] Recipes are tab-indented (checked with `cat -A`) - PASS

### Git hygiene

- [x] `.gitignore` keeps `.env` and `old versions/` and adds all 8 required entries - PASS
- [x] After `uv sync`, `make lint` and `make test`, `git status --porcelain` is empty. Generated `.venv/`, caches and `__pycache__/` show only as ignored - PASS
- [x] No `.env`, CSV, OFX/QFX, PDF or XLSX file in any commit (`git log --all --name-only`). Grepping full history for key/secret/token/password/private-key patterns finds only prose in `_docs/` and `AGENTS.md` - PASS

### CI

- [x] `.github/workflows/ci.yml` triggers on `push` (no branch filter) and `pull_request` - PASS
- [x] Steps: `actions/checkout@v5`, `astral-sh/setup-uv@v6`, `uv python install 3.13`, `uv sync --locked`, `make lint`, `make test` - PASS
- [x] `continue-on-error` does not appear anywhere in `.github/` - PASS
- [x] GitHub run `38998478003` for HEAD `65e94fb` finished `success`, and every step (Lint, Test included) succeeded (`gh run view`) - PASS

### README

- [x] Has the project name, the one-sentence description from the plan, a link to `_docs/plan.md`, and `uv sync`, `make lint`, `make test` - PASS
- [x] The badge uses the required URL and links to `.../actions/workflows/ci.yml` - PASS

### Notes (not failures)

- The failure cases (lint error, failing test) were only checked locally through `make`. CI runs the same `make` targets without `continue-on-error`, so it should fail the same way, but no failing run was seen on GitHub.
- I agree with the engineer's note: Ruff 0.17 also format-checks Python code blocks in the repo's Markdown files, so a badly formatted snippet in `_docs/` would fail `make lint` and CI.

Tests: `make test` on a fresh clone, 1 passed, 0 failed. `make lint`: `All checks passed!`, `20 files already formatted`.
