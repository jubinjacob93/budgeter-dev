"""String enums used by the models.

The database stores the lowercase values as VARCHAR with a named CHECK constraint, never a
native Postgres ENUM type, so adding a value later is a plain constraint change.
"""

from enum import StrEnum

from sqlalchemy import Enum


class Provider(StrEnum):
    SEED = "seed"
    CSV = "csv"
    MONARCH = "monarch"
    PLAID = "plaid"
    SIMPLEFIN = "simplefin"


class ConnectionStatus(StrEnum):
    ACTIVE = "active"
    LOGIN_REQUIRED = "login_required"
    ERROR = "error"
    DISCONNECTED = "disconnected"


class AccountType(StrEnum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT_CARD = "credit_card"
    BROKERAGE = "brokerage"
    RETIREMENT = "retirement"
    LOAN = "loan"
    OTHER = "other"


class OwnerTag(StrEnum):
    """Relative to the user who owns the account's connection (`connections.user_id`)."""

    MINE = "mine"
    PARTNER = "partner"
    JOINT = "joint"


def string_enum(enum_class: type[StrEnum], name: str) -> Enum:
    """A VARCHAR column type storing the enum's values, checked by `ck_<table>_<name>`."""
    return Enum(
        enum_class,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda members: [member.value for member in members],
    )
