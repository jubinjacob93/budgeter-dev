import os
from urllib.parse import urlsplit, urlunsplit

import pytest
from fastapi.testclient import TestClient

from budgeter.api.main import app
from budgeter.core.config import get_settings

DATABASE_URL = os.environ.get("DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not DATABASE_URL,
        reason="DATABASE_URL is not set; start the stack and export DATABASE_URL from .env",
    ),
]


@pytest.fixture
def client_for(monkeypatch):
    def make(database_url):
        monkeypatch.setenv("DATABASE_URL", database_url)
        get_settings.cache_clear()
        return TestClient(app)

    get_settings.cache_clear()
    yield make
    get_settings.cache_clear()


def with_wrong_password(database_url):
    parts = urlsplit(database_url)
    netloc = f"{parts.username}:wrong-password@{parts.hostname}"
    if parts.port:
        netloc += f":{parts.port}"
    return urlunsplit(parts._replace(netloc=netloc))


def test_health_ok_with_real_database(client_for):
    response = client_for(DATABASE_URL).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_health_503_with_wrong_password(client_for):
    response = client_for(with_wrong_password(DATABASE_URL)).get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}
