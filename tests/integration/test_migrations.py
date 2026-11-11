import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text

from budgeter.core.database import get_engine

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"),
        reason="DATABASE_URL is not set; start the stack and export DATABASE_URL from .env",
    ),
]

# These tests only upgrade, never downgrade, so they are safe on the development database.


def test_upgrade_head_enables_vector_and_reaches_script_head():
    config = Config(str(ALEMBIC_INI))

    command.upgrade(config, "head")

    with get_engine().connect() as conn:
        extensions = conn.execute(
            text("select extname from pg_extension where extname = 'vector'")
        ).all()
        current = MigrationContext.configure(conn).get_current_revision()

    assert len(extensions) == 1
    assert current == ScriptDirectory.from_config(config).get_current_head()
