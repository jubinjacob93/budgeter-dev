"""Shared SQLAlchemy models.

Import every model module here so `Base.metadata` (and so Alembic) sees all tables.
"""

from budgeter.core.models.account import Account
from budgeter.core.models.base import Base
from budgeter.core.models.category import Category
from budgeter.core.models.category_rule import CategoryRule
from budgeter.core.models.connection import Connection
from budgeter.core.models.enums import AccountType, ConnectionStatus, OwnerTag, Provider
from budgeter.core.models.merchant import Merchant
from budgeter.core.models.raw_transaction import RawTransaction
from budgeter.core.models.transaction import Transaction
from budgeter.core.models.transaction_split import TransactionSplit
from budgeter.core.models.user import User

__all__ = [
    "Account",
    "AccountType",
    "Base",
    "Category",
    "CategoryRule",
    "Connection",
    "ConnectionStatus",
    "Merchant",
    "OwnerTag",
    "Provider",
    "RawTransaction",
    "Transaction",
    "TransactionSplit",
    "User",
]
