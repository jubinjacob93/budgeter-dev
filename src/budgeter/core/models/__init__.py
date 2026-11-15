"""Shared SQLAlchemy models.

Import every model module here so `Base.metadata` (and so Alembic) sees all tables.
"""

from budgeter.core.models.account import Account
from budgeter.core.models.base import Base
from budgeter.core.models.connection import Connection
from budgeter.core.models.enums import AccountType, ConnectionStatus, OwnerTag, Provider
from budgeter.core.models.user import User

__all__ = [
    "Account",
    "AccountType",
    "Base",
    "Connection",
    "ConnectionStatus",
    "OwnerTag",
    "Provider",
    "User",
]
