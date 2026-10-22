import os
import subprocess
import sys

import pytest
from pydantic import ValidationError

from budgeter.core import config


@pytest.fixture(autouse=True)
def clear_settings_cache():
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def test_import_does_not_need_database_url():
    env = {key: value for key, value in os.environ.items() if key != "DATABASE_URL"}

    result = subprocess.run(
        [sys.executable, "-c", "import budgeter.core.config, budgeter.api.main"],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_settings_read_database_url_from_environment(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@example:5432/db")

    assert config.get_settings().database_url == "postgresql://user:pw@example:5432/db"


def test_settings_fail_when_database_url_unset(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(ValidationError):
        config.get_settings()
