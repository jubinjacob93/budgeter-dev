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


def count_users(engine):
    with engine.connect() as conn:
        return conn.execute(text("select count(*) from users")).scalar_one()


@pytest.fixture(scope="session")
def migrated_engine():
    """An engine for a database upgraded to head; checks that tests left no users behind."""
    command.upgrade(Config(str(ALEMBIC_INI)), "head")
    # Alembic's env.py used the cached app engine; drop it so tests start clean.
    get_engine().dispose()
    get_engine.cache_clear()
    get_settings.cache_clear()

    engine = build_engine(os.environ["DATABASE_URL"])
    users_before = count_users(engine)
    yield engine
    users_after = count_users(engine)
    engine.dispose()
    assert users_after == users_before, "integration tests left rows in users"


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
