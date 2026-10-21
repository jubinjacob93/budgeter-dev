import logging

import psycopg

logger = logging.getLogger(__name__)

# libpq's minimum; keeps /health well under 5 seconds when the database is down.
CONNECT_TIMEOUT_SECONDS = 2


def check_database(database_url: str) -> bool:
    """Return True if a connection can be opened and a trivial query runs.

    Failures are logged by error type only, so the URL and password never reach the logs.
    """
    try:
        with psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS) as conn:
            conn.execute("select 1")
    except psycopg.Error as exc:
        logger.warning("Database check failed: %s", type(exc).__name__)
        return False
    return True
