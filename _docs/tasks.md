# Backlog

Tasks for building the app described in `_docs/plan.md`, in build order. Each task is sized for one 2–3 hour session with AI assistance and is self-describing: read its goal, check that the tasks under **Depends on** are done, and see the referenced plan section for background. The milestone (M1–M8) is shown in each title. Tasks marked **optional** can be postponed without blocking anything else.

Tasks here are intentionally short. Before a task is implemented, the PM role grooms it into the full template in `_docs/task-template.md` (goal, acceptance criteria, out of scope, constraints), following `_docs/process.md`.

---

## 0. Set up the agent workflow (M1) ✅
Goal: Every coding-agent session starts with the project's rules, process and roles.
Depends on: none
Description: Add `AGENTS.md` (commands, rules, links to documents), `CLAUDE.md` pointing to it, `_docs/process.md`, `_docs/task-template.md`, and the three role files in `_docs/team/` (PM, software engineer, QA). Commit them before any code so every later session follows the same workflow.

## 1. Set up an empty project with a passing test and CI (M1) ✅
Goal: A clean Python project that installs, lints and passes one test, locally and in GitHub Actions.
Depends on: 0
Description: Initialize the repository with uv, the folder layout from the plan's Repository layout section, pytest and Ruff configured in `pyproject.toml`, a `.gitignore`, a README stub and one trivial test. Add a Makefile with `make test` and `make lint`, plus a GitHub Actions workflow that runs Ruff and pytest on every push and pull request, with its status badge in the README.

## 2. Run Postgres and a FastAPI skeleton in Docker Compose (M1)
Goal: `docker compose up` starts Postgres (with pgvector) and a FastAPI app with a health check.
Depends on: 1
Description: Create `docker-compose.yml` with a pgvector-enabled Postgres service (named volume, health check) and a FastAPI service built from its own Dockerfile. Add a `/health` endpoint that also checks the database connection, a test for it, and a `.env.example` for all settings, with `.env` git-ignored.

## 3. Set up SQLAlchemy and Alembic (M1)
Goal: The app connects to Postgres through SQLAlchemy and manages the schema with Alembic.
Depends on: 2
Description: Add a database module that builds a SQLAlchemy 2.0 engine and session from environment variables. Initialize Alembic with an initial migration that enables the `vector` extension, and add a CI step that runs all migrations against a fresh Postgres service container.

## 4. Create the users, connections and accounts tables (M1)
Goal: The core ownership tables exist as models with a migration.
Depends on: 3
Description: Model `users`, `connections` and `accounts` as described in the plan's data model, including `owner_tag` (Mine / Partner / Joint). Generate and apply the migration, and add tests that insert and read back sample rows.

## 5. Create the transaction and category tables (M1)
Goal: Tables for raw data, transactions, splits, merchants and categories exist with a migration.
Depends on: 4
Description: Model `raw_transactions`, `transactions`, `transaction_splits`, `merchants`, `categories` and `category_rules` per the plan's data model. Include a unique constraint on (provider, provider_txn_id) and a pgvector column on `merchants`; test the unique constraint.

## 6. Generate seed data: accounts, transactions and holdings (M1)
Goal: One command fills the database with a realistic fake household.
Depends on: 5
Description: Write a script that creates two users, checking, savings, credit card and brokerage accounts, 3+ years of everyday transactions (groceries, dining, gas, shopping) and a few investment holdings. Use a fixed random seed so every run produces identical data.

## 7. Generate seed data: special scenarios (M1)
Goal: Seed data contains every case later features must detect.
Depends on: 6
Description: Extend the seed script with monthly subscriptions (one with a price increase), a semi-annual bill, transfers between accounts, credit card payments, refunds, a few large one-off purchases and a Costco-style purchase suitable for splitting. Document each scenario so later tests can reference it.

## 8. Define the provider interface and normalized models (M2)
Goal: One contract that every data source implements.
Depends on: 7
Description: Define an abstract provider interface plus normalized account, transaction and holding models (see the plan's Ingestion section). Implement the interface for the seed data and test that its output matches the normalized models.

## 9. Build the idempotent ingestion pipeline (M2)
Goal: Provider data is stored raw, normalized and upserted without duplicates.
Depends on: 8
Description: Save raw payloads to `raw_transactions`, normalize them, and upsert into `accounts`, `transactions` and holdings. Test that running the same import twice leaves the database unchanged.

## 10. Add a CSV import provider (M2)
Goal: Transactions can be imported from a bank CSV file.
Depends on: 9
Description: Implement the provider interface for CSV files, with a small column-mapping config per bank format. Handle sign conventions and date formats, and test with synthetic CSV fixtures.

## 11. Add a Monarch Money export provider (M2)
Goal: Years of history can be imported from a Monarch Money CSV export.
Depends on: 9
Description: Implement the provider interface for Monarch's transaction export, mapping accounts, categories and notes into the normalized models. Test with a synthetic fixture that mimics the export format; never commit a real export.

## 12. Normalize merchant names (M2)
Goal: Messy bank descriptions map to clean, consistent merchant names.
Depends on: 9
Description: Write a rules-based normalizer that strips store numbers, card prefixes and noise (e.g. `SQ *BLUE BOTTLE #123` → `Blue Bottle`) and links transactions to `merchants`. Cover common patterns with table-driven tests.

## 13. Set up categories and the rules engine (M2)
Goal: A starting category list exists and merchant rules categorize transactions automatically.
Depends on: 12
Description: Choose the starting category list (reuse Monarch's categories from the export, or define a new set) and record the choice in the plan. Implement rule matching from `category_rules` during ingestion; rules must never be overridden by later automated steps. Test precedence and re-application after a rule changes.

## 14. Detect transfers and card payments (M2)
Goal: Money moving between the household's own accounts is excluded from spending.
Depends on: 9
Description: Detect opposite-amount pairs across the household's accounts within a short date window, plus credit card payments, and mark them `is_transfer`. Test against the seed scenarios so no card payment ever counts as spending.

## 15. Net refunds against their category (M2)
Goal: Refunds reduce spending in the original category instead of counting as income.
Depends on: 13
Description: Identify refunds (positive amounts from a merchant normally charged) and treat them as negative spending in the original category. Test with the seed refund scenarios, including a refund in a different month from the purchase.

## 16. Add user authentication (M2)
Goal: Each household member logs in with their own account.
Depends on: 4
Description: Compare 2–3 auth approaches (default candidate: hashed passwords + bearer tokens, per the plan's library defaults) and record the choice in the plan. Implement login with hashed passwords for up to two users and protect all API endpoints; test login, failed login and unauthorized access.

## 17. Build the transactions API (M2)
Goal: The API lists, filters and edits transactions.
Depends on: 13, 14, 16
Description: Add endpoints to list transactions with filters (date range, account, category, merchant, ownership tag) and pagination, and to edit category and notes. Test filtering and that edits persist.

## 18. Show a first screen: a basic transactions page (M2)
Goal: See real data in a browser early in the build.
Depends on: 17
Description: Add a Streamlit container to Docker Compose with a single page that lists transactions from the API, with date and account filters. All backend calls go through `ui/api_client.py`, never directly to the database. Authenticate with a development user from environment settings; the full login screen comes in task 43.

## 19. Build budgets and planned-vs-actual (M2)
Goal: The API returns planned, actual and remaining amounts per category per month.
Depends on: 15, 17
Description: Add the `budgets` table with fixed, flexible and non-monthly types and endpoints to set them. Implement the monthly calculation, excluding transfers and netting refunds, with tests using seed data.

## 20. Evaluate Plaid and SimpleFIN (M3)
Goal: Decide which bank provider(s) to use, with evidence.
Depends on: none
Description: Follow the evaluation plan in the plan's Ingestion section: check institution support in the Plaid dashboard without using Trial slots, then trial SimpleFIN for a month and confirm brokerages return holdings. Record the results and decision in the plan. No code.

## 21. Add the Plaid Link flow with encrypted token storage (M3)
Goal: A user can connect an institution through Plaid Link in sandbox mode, and the token is stored safely.
Depends on: 9, 16, 20
Description: Build an encryption helper for `connections.encrypted_token` using a key from an environment variable. Serve a small Plaid Link page from FastAPI, exchange the public token, and store the access token encrypted, requesting only Transactions, Balance and Investments. Test in Plaid's sandbox and confirm tokens never appear in logs or responses.

## 22. Sync transactions and holdings from Plaid (M3)
Goal: Plaid data flows through the ingestion pipeline.
Depends on: 21
Description: Implement the provider interface for Plaid: fetch accounts, balances, transactions and investment holdings, and pass them through the pipeline. Record Plaid error states (e.g. login required) on the connection.

## 23. Add a SimpleFIN provider (M3, only if chosen in task 20)
Goal: SimpleFIN data flows through the ingestion pipeline.
Depends on: 9, 20
Description: Claim a setup token and store the access URL encrypted (reuse the helper from task 21, or build it here if Plaid is not used). Fetch accounts, transactions and holdings in windows of at most 90 days with a few days of overlap, staying within ~24 requests per day.

## 24. Add the scheduler and Sync now (M3)
Goal: Syncs run every 3 hours and on demand.
Depends on: 22 or 23
Description: Add a scheduler container using APScheduler that syncs every connection every 3 hours, plus a Sync now API endpoint. Prevent overlapping syncs of the same connection and log each run's result.

## 25. Refresh investment prices with yfinance (M3)
Goal: Holdings are valued at current market prices.
Depends on: 9
Description: Add a job that fetches prices for all held tickers during market hours and stores them in `prices`. Handle unknown tickers and API failures by keeping the last known price.

## 26. Calculate net worth with manual assets (M3)
Goal: Net worth combines balances, holdings × prices and manual assets.
Depends on: 25
Description: Add the `manual_assets` table and endpoints, then compute net worth by account and ownership tag. Store daily `net_worth_snapshots` for history and test the calculation with seed data.

## 27. Choose an embedding model and build an embedding helper (M4)
Goal: One module turns text into vectors for every RAG feature.
Depends on: 3
Description: Compare 2–3 embedding options (per the plan's open decisions) and record the choice in the plan. Implement batched embedding with caching so unchanged text is never embedded twice.

## 28. Add fuzzy merchant search (M4)
Goal: A search for "walmart" finds every variant of that merchant.
Depends on: 12, 27
Description: Embed normalized merchant names into the pgvector column and implement similarity search with a relevance threshold. Test that seed variants match and unrelated merchants do not.

## 29. Suggest categories with an LLM and retrieval (M4)
Goal: Transactions no rule matches get a category suggestion grounded in past examples.
Depends on: 13, 27
Description: Retrieve the most similar past categorized transactions and ask Claude to choose a category with a confidence score. Store each suggestion with its confidence and test the flow with a mocked model response.

## 30. Add the review queue (M4)
Goal: Low-confidence suggestions wait for a person, and approvals can become rules.
Depends on: 17, 29
Description: Route low-confidence suggestions to `review_queue` and add API endpoints to approve, correct or reject them. An approval can optionally create a new category rule; test each path.

## 31. Create the MCP server with a first tool (M4)
Goal: A read-only MCP server exposes `spending_by_category`.
Depends on: 14, 15
Description: Set up the MCP server as its own container, connecting to Postgres through a dedicated read-only database role. Implement `spending_by_category` with validated parameters and test it without an LLM.

## 32. Add transaction query tools (M4)
Goal: The agent can compare periods and search transactions.
Depends on: 28, 31
Description: Implement `compare_periods` (category-level differences between two periods) and `search_transactions` (fuzzy merchant, category, amount and date filters) as described in the plan's AI section. Validate inputs and unit-test each tool.

## 33. Add budget, net worth and projection tools (M4)
Goal: The agent can answer budget, net worth and long-term "what if" questions.
Depends on: 19, 26, 31
Description: Implement `get_budget_status`, `get_net_worth` and `project_growth`. The projection takes starting balance, yearly contributions, yearly spending, expected return and years, and returns a year-by-year result computed in Python; test it against hand-calculated values.

## 34. Build the agent loop as a command-line script (M4)
Goal: Ask the agent a question from the terminal and get an answer built from tool calls.
Depends on: 31
Description: Write an MCP client that sends the question to the Claude API, runs the tool-use loop against the MCP server, and prints the answer and the tools called. Keeping it in the terminal makes the loop easy to debug before building a UI.

## 35. Add the Streamlit chat page and connect Claude Desktop (M4)
Goal: Chat with the agent from any browser or from Claude Desktop.
Depends on: 18, 34
Description: Build a Streamlit chat page on top of the agent loop, showing which tools each answer used, and disable it when no API key is configured. Document and test the Claude Desktop configuration for the MCP server, and confirm write requests are refused.

## 36. Upload and index personal documents (M4)
Goal: Uploaded documents are split into chunks and embedded for search.
Depends on: 27
Description: Add document upload (PDF and text), text extraction, chunking and embedding into `documents` and `document_chunks`. Keep uploaded files out of the repository and test with synthetic documents.

## 37. Add document search with citations (M4)
Goal: The agent answers questions from documents and cites its sources.
Depends on: 31, 36
Description: Implement the `search_documents` tool, returning the best-matching chunks with document name and location. Test that answers to sample questions cite the correct chunk.

## 38. Build the categorization eval (M4)
Goal: Categorization accuracy is measured, with and without retrieval.
Depends on: 29
Description: Create a labeled evaluation set from seed data and a script that reports accuracy for the rules + LLM pipeline with retrieval on and off. Save results to a file so runs can be compared over time.

## 39. Build the question-answering eval (M4)
Goal: Agent answers are measured against a golden set.
Depends on: 32, 33, 34
Description: Write golden questions with expected tool calls and expected facts, and a script that scores the agent's answers. Add a CI job that runs it on demand using an API key stored as a repository secret.

## 40. Build the document retrieval eval (M4)
Goal: Document search quality is measured.
Depends on: 37
Description: Write queries paired with the chunk that should be found, and a script that reports how often the correct chunk appears in the top results. Run it with the other evals on demand in CI.

## 41. Log every model call (M5)
Goal: Tokens, cost and latency are recorded for each Claude call.
Depends on: 34
Description: Add the `llm_calls` table and a wrapper around the Claude client that records model, input/output tokens, estimated cost, latency, tools called and status. Add a cost-per-day summary query and tests for the wrapper.

## 42. Add input and output guardrails (M5)
Goal: The agent refuses unsafe requests and ungrounded answers are flagged.
Depends on: 34
Description: Validate tool arguments (date ranges, result limits), decline write and off-topic requests, and flag answers containing numbers that appear in no tool result. Add a test for each guardrail.

## 43. Build the Streamlit app shell and login (M6)
Goal: A navigable Streamlit app that requires login.
Depends on: 16, 18
Description: Replace the development user from task 18 with a real login screen, and add page navigation and a global ownership filter (Mine / Partner / Joint). Make sure the layout works at phone width.

## 44. Build the transactions and review queue pages (M6)
Goal: Browse, edit and review transactions in the UI.
Depends on: 30, 43
Description: Expand the transactions page with filters and inline category and notes editing, and add a review queue page for approving or correcting LLM suggestions.

## 45. Build the budgets page (M6)
Goal: Set budgets and see planned vs. actual by month.
Depends on: 19, 43
Description: Add a page to set budgets by type and view planned, actual and remaining per category for the current and past months, highlighting categories over budget.

## 46. Build the spending charts page (M6)
Goal: See where money goes over time.
Depends on: 43
Description: Add charts for spending by category, by month and month over month, respecting the ownership filter and excluding transfers.

## 47. Build the net worth page (M6)
Goal: See net worth over time and manage manual assets.
Depends on: 26, 43
Description: Add a net worth page with a history chart, a breakdown by account and owner, and a form to add and update manual assets such as a home or vehicle.

## 48. Build the accounts page (M6)
Goal: See each bank connection's health and trigger a sync.
Depends on: 24, 43
Description: Add a page listing connections and accounts with status, last sync time and any provider errors, plus a Sync now button and a link to connect a new institution.

## 49. Support split transactions (M7, optional)
Goal: One purchase can be divided across several categories.
Depends on: 17, 44
Description: Add API endpoints and UI to split a transaction into parts using `transaction_splits`, validating that parts sum to the original amount. Budgets and charts must use the split amounts; test with the seed Costco-style purchase.

## 50. Detect recurring bills (M7, optional)
Goal: Subscriptions and bills are found automatically, with upcoming charges and price increases.
Depends on: 12, 31
Description: Detect merchants charged at a regular interval with similar amounts, store them in `recurring_series`, predict the next charge and flag price increases. Add the `get_recurring` MCP tool and test against the seed subscriptions.

## 51. Add ntfy push notifications (M7)
Goal: Phone alerts for budget overruns, large transactions and price increases.
Depends on: 19, 24
Description: Send ntfy notifications from the scheduler for budget overruns and transactions above a configurable threshold, plus price increases if task 50 is done. Make sure each alert is sent only once.

## 52. Send the weekly summary email (M7)
Goal: A weekly AI-written summary of household finances arrives by email.
Depends on: 34, 41
Description: Compare 2–3 email services and record the choice in the plan. Add a weekly job that gathers the week's data through the agent's tools, asks Claude for a short summary and emails it, logging the call like any other.

## 53. Add demo mode (M7)
Goal: Anyone can run the app on synthetic data with one command.
Depends on: 7, 43
Description: Implement `DEMO_MODE`, which loads seed data on startup and disables bank sync, notifications and email; chat works only if the user supplies an API key. Document the quickstart in the README.

## 54. Write the README with screenshots (M7)
Goal: The repository explains the project clearly to visitors.
Depends on: 53
Description: Write a README covering features, architecture (with the diagram), the demo-mode quickstart, configuration and the security model. Add screenshots and a short GIF recorded in demo mode.

## 55. Deploy to a VPS (M7)
Goal: The app runs always-on, reachable only over the private network.
Depends on: 24, 43
Description: Provision a small VPS with SSH keys, a firewall, Docker and Tailscale, then deploy the stack with production environment variables. Confirm every page, the scheduler and the chat work from a phone over Tailscale.

## 56. Set up backups and test a restore (M7)
Goal: Data can be recovered if the server fails.
Depends on: 55
Description: Schedule nightly Postgres backups to off-server storage with retention, then restore a backup into a fresh database and confirm the app runs against it. Document the restore steps.

---

## v2

## 57. Migrate to Railway (M8, v2)
Goal: The app runs on Railway with public HTTPS and hardened access.
Depends on: 56
Description: Follow the migration checklist in the plan's Deployment section: confirm pgvector support, restore the database, recreate services with private networking, harden login and rate limiting, expose the MCP server with authentication, and update Plaid redirect URLs.

## 58. Build a mobile-friendly frontend with Lovable (v2)
Goal: A polished, phone-first UI that uses the existing backend unchanged.
Depends on: 43–48
Description: Generate a React frontend in Lovable from the plan and the FastAPI OpenAPI spec, with every backend call in one services layer. Connect it to the existing API (configure CORS and bearer-token auth), confirm all pages match the Streamlit features, and keep the backend untouched.
