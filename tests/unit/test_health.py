import logging

import pytest
from fastapi.testclient import TestClient

from budgeter.api.main import app
from budgeter.api.routers.health import database_is_reachable
from budgeter.core.database import check_database


@pytest.fixture
def client_with_database(request):
    app.dependency_overrides[database_is_reachable] = lambda: request.param
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.parametrize("client_with_database", [True], indirect=True)
def test_health_ok_when_database_reachable(client_with_database):
    response = client_with_database.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


@pytest.mark.parametrize("client_with_database", [False], indirect=True)
def test_health_503_when_database_unreachable(client_with_database):
    response = client_with_database.get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "database": "unavailable"}


def test_openapi_lists_health():
    response = TestClient(app).get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]


def test_docs_page_loads():
    response = TestClient(app).get("/docs")

    assert response.status_code == 200


def test_check_database_failure_logs_error_type_only(caplog):
    # Port 1 on localhost refuses connections, so no database is needed.
    url = "postgresql://someuser:secret-password@127.0.0.1:1/somedb"

    with caplog.at_level(logging.WARNING, logger="budgeter.core.database"):
        assert check_database(url) is False

    assert len(caplog.records) == 1
    message = caplog.records[0].getMessage()
    assert "OperationalError" in message
    for secret in ("secret-password", "someuser", "127.0.0.1", url):
        assert secret not in message
