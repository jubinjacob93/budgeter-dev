import datetime as dt
from decimal import Decimal
from enum import StrEnum

import pytest
from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.elements import conv

from budgeter.core.models import (
    Account,
    AccountType,
    Base,
    Category,
    CategoryRule,
    Connection,
    ConnectionStatus,
    Merchant,
    OwnerTag,
    Provider,
    RawTransaction,
    Transaction,
    TransactionSplit,
    User,
)

TABLES = (
    "users",
    "connections",
    "accounts",
    "raw_transactions",
    "transactions",
    "transaction_splits",
    "merchants",
    "categories",
    "category_rules",
)
TABLES_WITH_CREATED_AT = tuple(
    t for t in TABLES if t not in {"raw_transactions", "transaction_splits"}
)


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
    "raw_transactions": {
        "id": (Integer, False, None),
        "connection_id": (Integer, False, None),
        "provider": (Enum, False, None),
        "provider_txn_id": (String, False, None),
        "payload": (JSONB, False, None),
        "fetched_at": (DateTime, False, "now()"),
    },
    "transactions": {
        "id": (Integer, False, None),
        "account_id": (Integer, False, None),
        "provider": (Enum, False, None),
        "provider_txn_id": (String, False, None),
        "date": (Date, False, None),
        "amount": (Numeric, False, None),
        "merchant_raw": (String, False, None),
        "merchant_id": (Integer, True, None),
        "category_id": (Integer, True, None),
        "is_transfer": (Boolean, False, "false"),
        "notes": (Text, True, None),
        "created_at": (DateTime, False, "now()"),
    },
    "transaction_splits": {
        "id": (Integer, False, None),
        "transaction_id": (Integer, False, None),
        "category_id": (Integer, False, None),
        "amount": (Numeric, False, None),
    },
    "merchants": {
        "id": (Integer, False, None),
        "normalized_name": (String, False, None),
        "created_at": (DateTime, False, "now()"),
    },
    "categories": {
        "id": (Integer, False, None),
        "name": (String, False, None),
        "group_name": (String, False, None),
        "created_at": (DateTime, False, "now()"),
    },
    "category_rules": {
        "id": (Integer, False, None),
        "pattern": (String, False, None),
        "category_id": (Integer, False, None),
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


@pytest.mark.parametrize(
    ("table_name", "column_name", "length"),
    [
        ("raw_transactions", "provider_txn_id", 255),
        ("transactions", "provider_txn_id", 255),
        ("transactions", "merchant_raw", 500),
        ("merchants", "normalized_name", 255),
        ("categories", "name", 100),
        ("categories", "group_name", 100),
        ("category_rules", "pattern", 255),
    ],
)
def test_new_string_column_sizes(table_name, column_name, length):
    assert table(table_name).columns[column_name].type.length == length


@pytest.mark.parametrize("table_name", ["transactions", "transaction_splits"])
def test_amount_is_signed_numeric_14_2_decimal(table_name):
    amount = table(table_name).c.amount.type

    assert (amount.precision, amount.scale, amount.asdecimal) == (14, 2, True)
    assert amount.compile(dialect=postgresql.dialect()) == "NUMERIC(14, 2)"
    # No CHECK on the sign: negative is money out, positive money in, zero is allowed.
    checks = [c for c in table(table_name).constraints if isinstance(c, CheckConstraint)]
    assert not any("amount" in str(c.sqltext) for c in checks)


def test_payload_is_jsonb_and_date_is_date():
    assert table("raw_transactions").c.payload.type.compile(dialect=postgresql.dialect()) == (
        "JSONB"
    )
    assert table("transactions").c.date.type.compile(dialect=postgresql.dialect()) == "DATE"
    assert table("transactions").c.date.index is True


def test_merchants_has_no_vector_column():
    columns = table("merchants").columns

    assert "embedding" not in columns
    assert not any("vector" in type(c.type).__name__.lower() for c in columns)


@pytest.mark.parametrize("table_name", TABLES_WITH_CREATED_AT)
def test_created_at_is_timestamptz(table_name):
    assert table(table_name).c.created_at.type.timezone is True


def test_fetched_at_is_timestamptz():
    assert table("raw_transactions").c.fetched_at.type.timezone is True


def test_encrypted_token_is_bytea():
    column_type = table("connections").c.encrypted_token.type

    assert column_type.compile(dialect=postgresql.dialect()) == "BYTEA"


@pytest.mark.parametrize(
    ("table_name", "column_name", "referred"),
    [
        ("connections", "user_id", "users.id"),
        ("accounts", "connection_id", "connections.id"),
        ("raw_transactions", "connection_id", "connections.id"),
        ("transactions", "account_id", "accounts.id"),
        ("transactions", "merchant_id", "merchants.id"),
        ("transactions", "category_id", "categories.id"),
        ("transaction_splits", "transaction_id", "transactions.id"),
        ("transaction_splits", "category_id", "categories.id"),
        ("category_rules", "category_id", "categories.id"),
    ],
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
    ("table_name", "unique_name", "columns"),
    [
        ("transactions", "uq_transactions_provider", ["provider", "provider_txn_id"]),
        ("raw_transactions", "uq_raw_transactions_provider", ["provider", "provider_txn_id"]),
        ("merchants", "uq_merchants_normalized_name", ["normalized_name"]),
        ("categories", "uq_categories_name", ["name"]),
        ("category_rules", "uq_category_rules_pattern", ["pattern"]),
    ],
)
def test_new_unique_constraints(table_name, unique_name, columns):
    uniques = [c for c in table(table_name).constraints if isinstance(c, UniqueConstraint)]

    assert [(c.name, [col.name for col in c.columns]) for c in uniques] == [(unique_name, columns)]


def test_no_unique_on_group_name_or_split_category():
    assert table("categories").c.group_name.unique is not True
    split_uniques = [
        c for c in table("transaction_splits").constraints if isinstance(c, UniqueConstraint)
    ]
    assert split_uniques == []


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
        ("raw_transactions", "provider", Provider),
        ("transactions", "provider", Provider),
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
    "raw_transactions": {
        "pk_raw_transactions",
        "fk_raw_transactions_connection_id_connections",
        "uq_raw_transactions_provider",
        "ck_raw_transactions_provider",
        "ix_raw_transactions_connection_id",
    },
    "transactions": {
        "pk_transactions",
        "fk_transactions_account_id_accounts",
        "fk_transactions_merchant_id_merchants",
        "fk_transactions_category_id_categories",
        "uq_transactions_provider",
        "ck_transactions_provider",
        "ix_transactions_account_id",
        "ix_transactions_merchant_id",
        "ix_transactions_category_id",
        "ix_transactions_date",
    },
    "transaction_splits": {
        "pk_transaction_splits",
        "fk_transaction_splits_transaction_id_transactions",
        "fk_transaction_splits_category_id_categories",
        "ix_transaction_splits_transaction_id",
        "ix_transaction_splits_category_id",
    },
    "merchants": {"pk_merchants", "uq_merchants_normalized_name"},
    "categories": {"pk_categories", "uq_categories_name"},
    "category_rules": {
        "pk_category_rules",
        "fk_category_rules_category_id_categories",
        "uq_category_rules_pattern",
        "ix_category_rules_category_id",
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
        (Account.transactions, Transaction.account),
        (Transaction.splits, TransactionSplit.transaction),
        (Merchant.transactions, Transaction.merchant),
        (Category.transactions, Transaction.category),
        (Category.rules, CategoryRule.category),
    ]

    for one, other in pairs:
        assert one.property.back_populates == other.key
        assert other.property.back_populates == one.key
        assert not one.property.cascade.delete
        assert not other.property.cascade.delete


def test_split_category_is_one_way_without_delete_cascade():
    prop = TransactionSplit.category.property

    assert prop.back_populates is None
    assert prop.backref is None
    assert prop.mapper.class_ is Category
    assert not prop.cascade.delete


def test_raw_transaction_repr_does_not_contain_payload():
    raw = RawTransaction(
        id=1,
        connection_id=2,
        provider=Provider.PLAID,
        provider_txn_id="txn-1",
        payload={"fake": True, "secret_marker": "payload-marker-123"},
    )

    text = repr(raw)

    assert "payload" not in text
    assert "payload-marker-123" not in text
    assert "fake" not in text
    assert "txn-1" in text


def test_transaction_repr_does_not_contain_notes():
    txn = Transaction(
        id=1,
        account_id=2,
        provider=Provider.CSV,
        provider_txn_id="txn-1",
        date=dt.date(2026, 1, 2),
        amount=Decimal("-42.10"),
        merchant_raw="SQ *TEST CAFE #001",
        notes="notes-marker-123",
    )

    text = repr(txn)

    assert "notes" not in text
    assert "notes-marker-123" not in text
    assert "-42.10" in text


@pytest.mark.parametrize(
    ("instance", "expected"),
    [
        (Merchant(id=1, normalized_name="Test Cafe"), "Merchant("),
        (Category(id=1, name="Coffee", group_name="Food"), "Category("),
        (CategoryRule(id=1, pattern="TEST CAFE", category_id=2), "CategoryRule("),
        (
            TransactionSplit(id=1, transaction_id=2, category_id=3, amount=Decimal("-1.00")),
            "TransactionSplit(",
        ),
    ],
)
def test_other_models_have_explicit_repr(instance, expected):
    assert type(instance).__repr__ is not Base.__repr__
    assert repr(instance).startswith(expected)


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
