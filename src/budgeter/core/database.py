import logging
from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, make_url, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from budgeter.core.config import get_settings

logger = logging.getLogger(__name__)

# libpq's minimum; keeps /health well under 5 seconds when the database is down.
CONNECT_TIMEOUT_SECONDS = 2

PSYCOPG_DRIVERNAME = "postgresql+psycopg"


def psycopg_url(database_url: str) -> URL:
    """Parse `database_url` and force the psycopg 3 driver.

    `postgresql://` would otherwise make SQLAlchemy load psycopg2, which is not installed.
    """
    url = make_url(database_url)
    if url.drivername in ("postgresql", PSYCOPG_DRIVERNAME):
        url = url.set(drivername=PSYCOPG_DRIVERNAME)
    return url


def build_engine(database_url: str) -> Engine:
    """Create an engine without connecting; connections open on first use."""
    return create_engine(
        psycopg_url(database_url),
        # Replaces connections that died while pooled, e.g. after a database restart.
        pool_pre_ping=True,
        connect_args={"connect_timeout": CONNECT_TIMEOUT_SECONDS},
        echo=False,
    )


@lru_cache
def get_engine() -> Engine:
    """The app's one engine, created on first use. Tests reset it with `cache_clear()`."""
    return build_engine(get_settings().database_url)


@lru_cache(maxsize=1)
def _session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_session_factory() -> sessionmaker[Session]:
    """The session factory bound to `get_engine()`; follows the engine when it is reset."""
    return _session_factory(get_engine())


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yield a session and close it afterwards, also on errors."""
    with get_session_factory()() as session:
        yield session


def check_database(engine: Engine) -> bool:
    """Return True if a connection can be opened and a trivial query runs.

    Failures are logged by error type only, so the URL and password never reach the logs.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except SQLAlchemyError as exc:
        logger.warning("Database check failed: %s", type(exc).__name__)
        return False
    return True
