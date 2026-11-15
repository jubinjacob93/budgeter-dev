from enum import StrEnum

import pytest
from sqlalchemy import (
    CHAR,
    CheckConstraint,
    DateTime,
    Enum,
    Integer,
    LargeBinary,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.elements import conv

from budgeter.core.models import (
    Account,
    AccountType,
    Base,
    Connection,
    ConnectionStatus,
    OwnerTag,
    Provider,
    User,
)

TABLES = ("users", "connections", "accounts")


def table(name):
    return Base.metadata.tables[name]


def server_default(column):
    """The server default as SQL text (`now()`, `active`), or None."""
    default = column.server_default
    if default is None or default is column.identity:
        return None
    return getattr(default.arg, "text", None) or str(default.arg)


# Columns: name -> (type class, nullable, server default)
EXPECTED_COLUMNS = {
    "users": {
        "id": (Integer, False, None),
        "email": (String, False, None),
        "password_hash": (String, False, None),
        "created_at": (DateTime, False, "now()"),
    },
    "connections": {
        "id": (Integer, False, None),
        "user_id": (Integer, False, None),
        "provider": (Enum, False, None),
        "encrypted_token": (LargeBinary, True, None),
        "status": (Enum, False, "active"),
        "created_at": (DateTime, False, "now()"),
    },
    "accounts": {
        "id": (Integer, False, None),
        "connection_id": (Integer, False, None),
        "provider_account_id": (String, False, None),
        "name": (String, False, None),
        "type": (Enum, False, None),
        "owner_tag": (Enum, False, "mine"),
        "balance": (Numeric, True, None),
        "currency": (CHAR, False, "USD"),
        "created_at": (DateTime, False, "now()"),
    },
}


@pytest.mark.parametrize("table_name", TABLES)
def test_table_has_expected_columns(table_name):
    columns = table(table_name).columns
    expected = EXPECTED_COLUMNS[table_name]

    assert set(columns.keys()) == set(expected)
    for name, (type_class, nullable, default) in expected.items():
        column = columns[name]
        assert isinstance(column.type, type_class), name
        assert column.nullable is nullable, name
        assert server_default(column) == default, name


@pytest.mark.parametrize("table_name", TABLES)
def test_id_is_identity_primary_key(table_name):
    column = table(table_name).columns["id"]

    assert column.primary_key
    assert column.identity is not None


def test_column_sizes():
    assert table("users").c.email.type.length == 320
    assert table("users").c.password_hash.type.length == 255
    assert table("accounts").c.provider_account_id.type.length == 255
    assert table("accounts").c.name.type.length == 255
    assert table("accounts").c.currency.type.length == 3
    balance = table("accounts").c.balance.type
    assert (balance.precision, balance.scale, balance.asdecimal) == (14, 2, True)


@pytest.mark.parametrize("table_name", TABLES)
def test_created_at_is_timestamptz(table_name):
    assert table(table_name).c.created_at.type.timezone is True


def test_encrypted_token_is_bytea():
    column_type = table("connections").c.encrypted_token.type

    assert column_type.compile(dialect=postgresql.dialect()) == "BYTEA"


@pytest.mark.parametrize(
    ("table_name", "column_name", "referred"),
    [("connections", "user_id", "users.id"), ("accounts", "connection_id", "connections.id")],
)
def test_foreign_keys_restrict_and_are_indexed(table_name, column_name, referred):
    column = table(table_name).columns[column_name]
    (foreign_key,) = column.foreign_keys

    assert foreign_key.target_fullname == referred
    assert foreign_key.ondelete == "RESTRICT"
    assert column.index is True


def test_users_email_unique_and_lowercase_check():
    constraints = table("users").constraints
    uniques = [c for c in constraints if isinstance(c, UniqueConstraint)]
    checks = {c.name: str(c.sqltext) for c in constraints if isinstance(c, CheckConstraint)}

    assert [[col.name for col in c.columns] for c in uniques] == [["email"]]
    assert checks["ck_users_email_lowercase"] == "email = lower(email)"


def test_accounts_unique_on_connection_and_provider_account_id():
    uniques = [c for c in table("accounts").constraints if isinstance(c, UniqueConstraint)]

    assert [[col.name for col in c.columns] for c in uniques] == [
        ["connection_id", "provider_account_id"]
    ]


@pytest.mark.parametrize(
    ("enum_class", "values"),
    [
        (Provider, ["seed", "csv", "monarch", "plaid", "simplefin"]),
        (ConnectionStatus, ["active", "login_required", "error", "disconnected"]),
        (
            AccountType,
            ["checking", "savings", "credit_card", "brokerage", "retirement", "loan", "other"],
        ),
        (OwnerTag, ["mine", "partner", "joint"]),
    ],
)
def test_enum_values(enum_class, values):
    assert issubclass(enum_class, StrEnum)
    assert [member.value for member in enum_class] == values


@pytest.mark.parametrize(
    ("table_name", "column_name", "enum_class"),
    [
        ("connections", "provider", Provider),
        ("connections", "status", ConnectionStatus),
        ("accounts", "type", AccountType),
        ("accounts", "owner_tag", OwnerTag),
    ],
)
def test_enum_columns_store_values_as_checked_varchar(table_name, column_name, enum_class):
    column_type = table(table_name).columns[column_name].type

    assert column_type.native_enum is False
    assert column_type.create_constraint is True
    # The database stores the lowercase values, not the member names.
    assert column_type.enums == [member.value for member in enum_class]
    assert column_type.compile(dialect=postgresql.dialect()).startswith("VARCHAR")


EXPECTED_CONSTRAINT_NAMES = {
    "users": {"pk_users", "uq_users_email", "ck_users_email_lowercase"},
    "connections": {
        "pk_connections",
        "fk_connections_user_id_users",
        "ck_connections_provider",
        "ck_connections_status",
        "ix_connections_user_id",
    },
    "accounts": {
        "pk_accounts",
        "fk_accounts_connection_id_connections",
        "uq_accounts_connection_id",
        "ck_accounts_type",
        "ck_accounts_owner_tag",
        "ix_accounts_connection_id",
    },
}


@pytest.mark.parametrize("table_name", TABLES)
def test_every_constraint_and_index_has_a_convention_name(table_name):
    t = table(table_name)
    items = [*t.constraints, *t.indexes]
    names = [item.name for item in items]

    assert None not in names
    # `conv` means the name came from the naming convention in core/models/base.py.
    assert all(isinstance(name, conv) for name in names)
    assert len(names) == len(set(names))
    assert set(names) == EXPECTED_CONSTRAINT_NAMES[table_name]


def test_relationships_back_populate_without_delete_cascade():
    pairs = [
        (User.connections, Connection.user),
        (Connection.accounts, Account.connection),
    ]

    for one, other in pairs:
        assert one.property.back_populates == other.key
        assert other.property.back_populates == one.key
        assert not one.property.cascade.delete
        assert not other.property.cascade.delete


def test_connection_repr_does_not_contain_token():
    token = b"not-a-real-token"
    connection = Connection(
        id=1, user_id=2, provider=Provider.PLAID, status=ConnectionStatus.ACTIVE
    )
    connection.encrypted_token = token

    text = repr(connection)

    assert "not-a-real-token" not in text
    assert repr(token) not in text
    assert "encrypted_token" not in text
    assert "plaid" in text
