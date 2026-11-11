import os
import subprocess
import sys

import pytest
from sqlalchemy import Engine

from budgeter.core import database
from budgeter.core.config import get_settings
from budgeter.core.models import Base


@pytest.fixture(autouse=True)
def reset_settings_and_engine():
    get_settings.cache_clear()
    database.get_engine.cache_clear()
    yield
    get_settings.cache_clear()
    database.get_engine.cache_clear()


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:pw@example:5432/db",
        "postgresql+psycopg://user:pw@example:5432/db",
    ],
)
def test_engine_uses_psycopg3_driver(monkeypatch, database_url):
    monkeypatch.setenv("DATABASE_URL", database_url)

    engine = database.get_engine()

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.host == "example"
    assert engine.url.database == "db"


def test_engine_is_created_once_and_reused(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@example:5432/db")

    first = database.get_engine()

    assert isinstance(first, Engine)
    assert database.get_engine() is first


def test_engine_settings(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@example:5432/db")

    engine = database.get_engine()

    assert engine.pool._pre_ping is True
    assert engine.echo is False
    assert database.CONNECT_TIMEOUT_SECONDS == 2


def test_session_factory_follows_engine_reset(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@example:5432/db")
    factory = database.get_session_factory()

    assert factory.kw["bind"] is database.get_engine()
    assert factory.kw["expire_on_commit"] is False

    database.get_engine.cache_clear()

    assert database.get_session_factory().kw["bind"] is database.get_engine()


def test_get_session_closes_session_when_caller_raises(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@example:5432/db")
    closed = []
    dependency = database.get_session()
    session = next(dependency)
    monkeypatch.setattr(session, "close", lambda: closed.append(True))

    with pytest.raises(RuntimeError):
        dependency.throw(RuntimeError("endpoint failed"))

    assert closed == [True]


def test_import_does_not_create_engine():
    env = {key: value for key, value in os.environ.items() if key != "DATABASE_URL"}
    code = (
        "import budgeter.core.database as d, budgeter.api.main\n"
        "assert d.get_engine.cache_info().currsize == 0\n"
    )

    result = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)

    assert result.returncode == 0, result.stderr


def test_base_metadata_has_naming_convention_and_no_tables():
    convention = Base.metadata.naming_convention

    assert {"ix", "uq", "ck", "fk", "pk"} <= convention.keys()
    assert Base.metadata.tables == {}
