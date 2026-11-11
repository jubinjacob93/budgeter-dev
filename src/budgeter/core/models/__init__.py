"""Shared SQLAlchemy models.

Import every model module here so `Base.metadata` (and so Alembic) sees all tables.
"""

from budgeter.core.models.base import Base

__all__ = ["Base"]
