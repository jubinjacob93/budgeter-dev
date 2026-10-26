from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from budgeter.api.schemas.health import HealthResponse
from budgeter.core.config import get_settings
from budgeter.core.database import check_database

router = APIRouter(tags=["health"])


def database_is_reachable() -> bool:
    return check_database(get_settings().database_url)


# A plain `def` endpoint runs in FastAPI's thread pool, so the blocking check
# does not stall the event loop.
@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
)
def health(
    response: Response,
    database_ok: Annotated[bool, Depends(database_is_reachable)],
) -> HealthResponse:
    if database_ok:
        return HealthResponse(status="ok", database="ok")
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return HealthResponse(status="error", database="unavailable")
