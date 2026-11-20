import datetime as dt
import os
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from budgeter.core.models import (
    Account,
    AccountType,
    Category,
    CategoryRule,
    Connection,
    Merchant,
    Provider,
    RawTransaction,
    Transaction,
    TransactionSplit,
    User,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"),
        reason="DATABASE_URL is not set; start the stack and export DATABASE_URL from .env",
    ),
]

TXN_DATE = dt.date(2026, 1, 15)


# Made-up fixtures only.


def make_account(session, provider=Provider.PLAID, provider_account_id="acc-1"):
    user = session.scalars(select(User).where(User.email == "t05@example.com")).one_or_none()
    if user is None:
        user = User(email="t05@example.com", password_hash="not-a-real-hash")
    connection = Connection(user=user, provider=provider)
    account = Account(
        connection=connection,
        provider_account_id=provider_account_id,
        name="Fake Checking",
        type=AccountType.CHECKING,
    )
    session.add(account)
    session.flush()
    return account


def make_category(session, name="Coffee", group_name="Food"):
    category = Category(name=name, group_name=group_name)
    session.add(category)
    session.flush()
    return category


def make_merchant(session, normalized_name="Test Cafe"):
    merchant = Merchant(normalized_name=normalized_name)
    session.add(merchant)
    session.flush()
    return merchant


def make_transaction(session, account, provider_txn_id="txn-1", provider=None, **fields):
    fields.setdefault("date", TXN_DATE)
    fields.setdefault("amount", Decimal("-4.50"))
    fields.setdefault("merchant_raw", "SQ *TEST CAFE #001")
    txn = Transaction(
        account=account,
        provider=provider or account.connection.provider,
        provider_txn_id=provider_txn_id,
        **fields,
    )
    session.add(txn)
    session.flush()
    return txn


def make_raw(session, connection, provider_txn_id="txn-1", provider=None, payload=None):
    raw = RawTransaction(
        connection_id=connection.id,
        provider=provider or connection.provider,
        provider_txn_id=provider_txn_id,
        payload={"fake": True} if payload is None else payload,
    )
    session.add(raw)
    session.flush()
    return raw


def expect_integrity_error(session, statement, **params):
    """Run raw SQL that must fail; only its savepoint is rolled back."""
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(text(statement), params)


def insert_transaction_sql(**overrides):
    """Raw SQL insert into transactions with valid defaults that the caller can override."""
    values = {
        "account_id": ":account_id",
        "provider": "'plaid'",
        "provider_txn_id": "'raw-sql-1'",
        "date": "'2026-01-15'",
        "amount": "-1.00",
        "merchant_raw": "'SQ *TEST CAFE #001'",
        **overrides,
    }
    return f"insert into transactions ({', '.join(values)}) values ({', '.join(values.values())})"


def test_insert_and_read_back_through_relationships(db_session):
    account = make_account(db_session)
    coffee = make_category(db_session, "Coffee", "Food")
    snacks = make_category(db_session, "Snacks", "Food")
    merchant = make_merchant(db_session, "Test Cafe")
    db_session.add(CategoryRule(pattern="TEST CAFE", category=coffee))
    txn = make_transaction(
        db_session,
        account,
        "txn-full",
        amount=Decimal("-12.30"),
        merchant=merchant,
        category=coffee,
        is_transfer=False,
        notes="fake note",
    )
    txn.splits = [
        TransactionSplit(category=coffee, amount=Decimal("-10.00")),
        TransactionSplit(category=snacks, amount=Decimal("-2.30")),
    ]
    db_session.commit()
    ids = {"txn": txn.id, "account": account.id, "merchant": merchant.id, "coffee": coffee.id}
    db_session.expunge_all()

    loaded = db_session.scalars(select(Transaction).where(Transaction.id == ids["txn"])).one()

    assert loaded.account_id == ids["account"]
    assert loaded.provider is Provider.PLAID
    assert loaded.provider_txn_id == "txn-full"
    assert loaded.date == TXN_DATE
    assert loaded.amount == Decimal("-12.30")
    assert loaded.merchant_raw == "SQ *TEST CAFE #001"
    assert loaded.merchant_id == ids["merchant"]
    assert loaded.category_id == ids["coffee"]
    assert loaded.is_transfer is False
    assert loaded.notes == "fake note"
    assert loaded.created_at.tzinfo is not None
    # Account.transactions <-> Transaction.account
    assert loaded.account.id == ids["account"]
    assert loaded in loaded.account.transactions
    # Merchant.transactions <-> Transaction.merchant
    assert loaded.merchant.normalized_name == "Test Cafe"
    assert loaded.merchant.created_at is not None
    assert loaded.merchant.transactions == [loaded]
    # Category.transactions <-> Transaction.category, Category.rules <-> CategoryRule.category
    assert (loaded.category.name, loaded.category.group_name) == ("Coffee", "Food")
    assert loaded.category.transactions == [loaded]
    (loaded_rule,) = loaded.category.rules
    assert loaded_rule.pattern == "TEST CAFE"
    assert loaded_rule.category is loaded.category
    assert loaded_rule.created_at is not None
    # Transaction.splits <-> TransactionSplit.transaction, TransactionSplit.category
    splits = sorted(loaded.splits, key=lambda s: s.amount)
    assert [(s.category.name, s.amount) for s in splits] == [
        ("Coffee", Decimal("-10.00")),
        ("Snacks", Decimal("-2.30")),
    ]
    assert all(s.transaction is loaded for s in splits)


def test_several_splits_may_share_a_category(db_session):
    account = make_account(db_session)
    coffee = make_category(db_session)
    txn = make_transaction(db_session, account, amount=Decimal("-3.00"))
    txn.splits = [
        TransactionSplit(category=coffee, amount=Decimal("-1.00")),
        TransactionSplit(category=coffee, amount=Decimal("-2.00")),
    ]
    db_session.commit()

    count = db_session.execute(
        text("select count(*) from transaction_splits where transaction_id = :id"), {"id": txn.id}
    ).scalar_one()
    assert count == 2


def test_transaction_unique_on_provider_and_provider_txn_id(db_session):
    first = make_account(db_session, Provider.PLAID, "acc-1")
    other = make_account(db_session, Provider.PLAID, "acc-2")
    make_transaction(db_session, first, "dup-1")

    # Same pair, same account.
    expect_integrity_error(
        db_session,
        insert_transaction_sql(provider_txn_id="'dup-1'"),
        account_id=first.id,
    )
    # Same pair, another account.
    expect_integrity_error(
        db_session,
        insert_transaction_sql(provider_txn_id="'dup-1'"),
        account_id=other.id,
    )
    # Same provider_txn_id under a different provider succeeds.
    make_transaction(db_session, other, "dup-1", provider=Provider.SIMPLEFIN)
    db_session.commit()

    providers = db_session.scalars(
        select(Transaction.provider).where(Transaction.provider_txn_id == "dup-1")
    )
    assert sorted(providers) == [Provider.PLAID, Provider.SIMPLEFIN]


def test_raw_transaction_unique_on_provider_and_provider_txn_id(db_session):
    first = make_account(db_session, Provider.PLAID, "acc-1").connection
    other = make_account(db_session, Provider.PLAID, "acc-2").connection
    make_raw(db_session, first, "dup-1")
    statement = (
        "insert into raw_transactions (connection_id, provider, provider_txn_id, payload) "
        "values (:cid, :provider, 'dup-1', '{\"fake\": true}')"
    )

    # Same pair, same connection.
    expect_integrity_error(db_session, statement, cid=first.id, provider="plaid")
    # Same pair, another connection.
    expect_integrity_error(db_session, statement, cid=other.id, provider="plaid")
    # Same provider_txn_id under a different provider succeeds.
    make_raw(db_session, other, "dup-1", provider=Provider.SIMPLEFIN)
    db_session.commit()

    providers = db_session.scalars(
        select(RawTransaction.provider).where(RawTransaction.provider_txn_id == "dup-1")
    )
    assert sorted(providers) == [Provider.PLAID, Provider.SIMPLEFIN]


def test_nested_payload_round_trips_exactly(db_session):
    connection = make_account(db_session).connection
    payload = {
        "fake": True,
        "amount": "12.30",
        "count": 3,
        "ratio": 0.5,
        "missing": None,
        "name": "Café ☕ — テスト",
        "tags": ["a", None, 1, {"deep": [[], {}]}],
        "location": {"city": None, "coords": [1.25, -2.5]},
    }
    raw = make_raw(db_session, connection, "payload-1", payload=payload)
    db_session.commit()
    raw_id, connection_id = raw.id, connection.id
    db_session.expunge_all()

    loaded = db_session.get(RawTransaction, raw_id)

    assert loaded.payload == payload
    assert loaded.payload["amount"] == "12.30"
    assert loaded.connection_id == connection_id
    assert loaded.fetched_at.tzinfo is not None


@pytest.mark.parametrize("amount", [Decimal("-42.10"), Decimal("1500.00"), Decimal("0.00")])
def test_signed_amount_round_trips_and_is_transfer_defaults_false(db_session, amount):
    account = make_account(db_session)
    txn_id = db_session.execute(
        text(insert_transaction_sql(amount=":amount") + " returning id"),
        {"account_id": account.id, "amount": amount},
    ).scalar_one()
    db_session.commit()
    db_session.expunge_all()

    loaded = db_session.get(Transaction, txn_id)

    assert isinstance(loaded.amount, Decimal)
    assert loaded.amount == amount
    assert str(loaded.amount) == str(amount)
    assert loaded.is_transfer is False
    assert loaded.created_at is not None


def test_split_amount_round_trips_exactly(db_session):
    account = make_account(db_session)
    category = make_category(db_session)
    txn = make_transaction(db_session, account, amount=Decimal("-42.10"))
    split = TransactionSplit(transaction=txn, category=category, amount=Decimal("-42.10"))
    db_session.add(split)
    db_session.commit()
    split_id = split.id
    db_session.expunge_all()

    assert str(db_session.get(TransactionSplit, split_id).amount) == "-42.10"


def test_uncategorized_transaction_without_merchant_saves(db_session):
    account = make_account(db_session)
    txn = make_transaction(db_session, account, "uncategorized-1")
    db_session.commit()
    txn_id = txn.id
    db_session.expunge_all()

    loaded = db_session.get(Transaction, txn_id)

    assert loaded.merchant_id is None
    assert loaded.category_id is None
    assert loaded.merchant is None
    assert loaded.category is None
    uncategorized = db_session.scalars(
        select(Transaction.id).where(Transaction.category_id.is_(None))
    )
    assert txn_id in list(uncategorized)


@pytest.mark.parametrize("provider", ["mint", "PLAID", ""])
def test_unknown_provider_is_rejected_on_transactions(db_session, provider):
    account = make_account(db_session)

    expect_integrity_error(
        db_session,
        insert_transaction_sql(provider=":provider"),
        account_id=account.id,
        provider=provider,
    )


@pytest.mark.parametrize("provider", ["mint", "PLAID", ""])
def test_unknown_provider_is_rejected_on_raw_transactions(db_session, provider):
    connection = make_account(db_session).connection

    expect_integrity_error(
        db_session,
        "insert into raw_transactions (connection_id, provider, provider_txn_id, payload) "
        "values (:cid, :provider, 'x', '{}')",
        cid=connection.id,
        provider=provider,
    )


@pytest.mark.parametrize(
    "case",
    [
        "transactions.account_id",
        "transactions.merchant_id",
        "transactions.category_id",
        "transaction_splits.transaction_id",
        "transaction_splits.category_id",
        "category_rules.category_id",
        "raw_transactions.connection_id",
    ],
)
def test_foreign_key_to_missing_row_is_rejected(db_session, case):
    account = make_account(db_session)
    category = make_category(db_session)
    txn = make_transaction(db_session, account)
    statements = {
        "transactions.account_id": insert_transaction_sql(account_id="-1"),
        "transactions.merchant_id": insert_transaction_sql(merchant_id="-1"),
        "transactions.category_id": insert_transaction_sql(category_id="-1"),
        "transaction_splits.transaction_id": (
            "insert into transaction_splits (transaction_id, category_id, amount) "
            "values (-1, :category_id, -1.00)"
        ),
        "transaction_splits.category_id": (
            "insert into transaction_splits (transaction_id, category_id, amount) "
            "values (:txn_id, -1, -1.00)"
        ),
        "category_rules.category_id": (
            "insert into category_rules (pattern, category_id) values ('MISSING', -1)"
        ),
        "raw_transactions.connection_id": (
            "insert into raw_transactions (connection_id, provider, provider_txn_id, payload) "
            "values (-1, 'plaid', 'missing-1', '{}')"
        ),
    }
    params = {"account_id": account.id, "category_id": category.id, "txn_id": txn.id}
    statement = statements[case]

    expect_integrity_error(
        db_session, statement, **{k: v for k, v in params.items() if f":{k}" in statement}
    )


def test_deleting_account_with_transactions_is_restricted(db_session):
    account = make_account(db_session)
    make_transaction(db_session, account)

    expect_integrity_error(db_session, "delete from accounts where id = :id", id=account.id)


def test_deleting_merchant_with_transactions_is_restricted(db_session):
    merchant = make_merchant(db_session)
    make_transaction(db_session, make_account(db_session), merchant=merchant)

    expect_integrity_error(db_session, "delete from merchants where id = :id", id=merchant.id)


@pytest.mark.parametrize("used_by", ["transaction", "split", "rule"])
def test_deleting_category_in_use_is_restricted(db_session, used_by):
    category = make_category(db_session)
    if used_by == "transaction":
        make_transaction(db_session, make_account(db_session), category=category)
    elif used_by == "split":
        txn = make_transaction(db_session, make_account(db_session))
        db_session.add(TransactionSplit(transaction=txn, category=category, amount=Decimal("-1")))
    else:
        db_session.add(CategoryRule(pattern="TEST CAFE", category=category))
    db_session.flush()

    expect_integrity_error(db_session, "delete from categories where id = :id", id=category.id)


def test_deleting_transaction_with_splits_is_restricted(db_session):
    txn = make_transaction(db_session, make_account(db_session))
    db_session.add(
        TransactionSplit(transaction=txn, category=make_category(db_session), amount=Decimal("-1"))
    )
    db_session.flush()

    expect_integrity_error(db_session, "delete from transactions where id = :id", id=txn.id)


def test_deleting_connection_with_raw_transactions_is_restricted(db_session):
    account = make_account(db_session)
    connection = account.connection
    make_raw(db_session, connection)
    # Remove the account first so only the raw transaction holds the connection.
    db_session.delete(account)
    db_session.flush()

    expect_integrity_error(db_session, "delete from connections where id = :id", id=connection.id)


def test_duplicate_merchant_name_is_rejected_but_case_variants_are_allowed(db_session):
    make_merchant(db_session, "Blue Bottle")

    expect_integrity_error(
        db_session, "insert into merchants (normalized_name) values ('Blue Bottle')"
    )
    make_merchant(db_session, "blue bottle")
    db_session.commit()

    names = db_session.scalars(
        select(Merchant.normalized_name).where(Merchant.normalized_name.ilike("blue bottle"))
    )
    assert sorted(names) == ["Blue Bottle", "blue bottle"]


def test_duplicate_category_name_is_rejected_but_groups_are_shared(db_session):
    make_category(db_session, "Coffee", "Food")

    expect_integrity_error(
        db_session, "insert into categories (name, group_name) values ('Coffee', 'Other')"
    )
    make_category(db_session, "Groceries", "Food")
    db_session.commit()

    names = db_session.scalars(select(Category.name).where(Category.group_name == "Food"))
    assert sorted(names) == ["Coffee", "Groceries"]


def test_duplicate_rule_pattern_is_rejected_but_patterns_may_share_a_category(db_session):
    coffee = make_category(db_session, "Coffee", "Food")
    other = make_category(db_session, "Snacks", "Food")
    db_session.add(CategoryRule(pattern="TEST CAFE", category=coffee))
    db_session.flush()

    expect_integrity_error(
        db_session,
        "insert into category_rules (pattern, category_id) values ('TEST CAFE', :cid)",
        cid=other.id,
    )
    db_session.add(CategoryRule(pattern="TEST COFFEE BAR", category=coffee))
    db_session.commit()

    patterns = db_session.scalars(
        select(CategoryRule.pattern).where(CategoryRule.category_id == coffee.id)
    )
    assert sorted(patterns) == ["TEST CAFE", "TEST COFFEE BAR"]
