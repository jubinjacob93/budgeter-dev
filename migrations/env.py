from logging.config import fileConfig

from alembic import context

from budgeter.core.database import get_engine
from budgeter.core.models import Base

config = context.config

# Keep loggers created before this point (e.g. when tests call Alembic's Python API).
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    # The engine comes from DATABASE_URL via core/config.py. The URL is never put into the
    # Alembic config, so a `%` in an encoded password cannot break config interpolation.
    with get_engine().connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("Offline mode (--sql) is not supported; run migrations against a database.")

run_migrations_online()
