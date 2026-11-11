import pytest

from budgeter.core.config import get_settings
from budgeter.core.database import get_engine


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
