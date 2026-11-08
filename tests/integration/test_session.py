import os

import pytest
from sqlalchemy import select

from budgeter.core.database import get_session

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"),
        reason="DATABASE_URL is not set; start the stack and export DATABASE_URL from .env",
    ),
]


def test_select_1_through_get_session():
    dependency = get_session()
    session = next(dependency)

    assert session.execute(select(1)).scalar_one() == 1

    dependency.close()
