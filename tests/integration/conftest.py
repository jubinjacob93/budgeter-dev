import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.orm import Session

from budgeter.core.config import get_settings
from budgeter.core.database import build_engine, get_engine

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"


@pytest.fixture(autouse=True)
def reset_settings_and_engine():
    """Every integration test starts and ends with fresh settings and a fresh engine."""
    get_settings.cache_clear()
    get_engine.cache_clear()
    yield
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_settings.cache_clear()
    get_engine.cache_clear()


# Tables whose row counts must be the same before and after the test run.
CHECKED_TABLES = (
    "users",
    "transactions",
    "raw_transactions",
    "merchants",
    "categories",
    "category_rules",
)


def count_rows(engine):
    with engine.connect() as conn:
        return {
            table: conn.execute(text(f"select count(*) from {table}")).scalar_one()
            for table in CHECKED_TABLES
        }


@pytest.fixture(scope="session")
def migrated_engine():
    """An engine for a database upgraded to head; checks that tests left no rows behind."""
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    # Alembic's env.py used the cached app engine; drop it so tests start clean.
    get_engine().dispose()
    get_engine.cache_clear()
    get_settings.cache_clear()

    engine = build_engine(os.environ["DATABASE_URL"])
    rows_before = count_rows(engine)
    yield engine
    rows_after = count_rows(engine)
    engine.dispose()
    assert rows_after == rows_before, "integration tests left rows behind"


@pytest.fixture
def db_session(migrated_engine):
    """A session inside an outer transaction that is rolled back after the test.

    `session.commit()` only releases a savepoint, and a failed statement wrapped in
    `session.begin_nested()` rolls back to its own savepoint, so the test can continue.
    """
    with migrated_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint")
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()
