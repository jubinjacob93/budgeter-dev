import os
from decimal import Decimal

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from budgeter.core.models import (
    Account,
    AccountType,
    Connection,
    ConnectionStatus,
    OwnerTag,
    Provider,
    User,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not os.environ.get("DATABASE_URL"),
        reason="DATABASE_URL is not set; start the stack and export DATABASE_URL from .env",
    ),
]

FAKE_TOKEN = b"not-a-real-token"


def make_user(session, email="alice@example.com"):
    user = User(email=email, password_hash="not-a-real-hash")
    session.add(user)
    session.flush()
    return user


def make_connection(session, user, provider=Provider.SEED, **fields):
    connection = Connection(user=user, provider=provider, **fields)
    session.add(connection)
    session.flush()
    return connection


def make_account(session, connection, provider_account_id="acc-1", **fields):
    fields.setdefault("name", "Everyday Checking")
    fields.setdefault("type", AccountType.CHECKING)
    account = Account(connection=connection, provider_account_id=provider_account_id, **fields)
    session.add(account)
    session.flush()
    return account


def expect_integrity_error(session, statement, **params):
    """Run raw SQL that must fail; only its savepoint is rolled back."""
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(text(statement), params)


def test_insert_and_read_back_through_relationships(db_session):
    user = make_user(db_session)
    connection = make_connection(
        db_session, user, Provider.PLAID, encrypted_token=FAKE_TOKEN, status=ConnectionStatus.ERROR
    )
    make_account(
        db_session,
        connection,
        "chk-1",
        name="Checking",
        type=AccountType.CHECKING,
        owner_tag=OwnerTag.MINE,
        balance=Decimal("100.10"),
        currency="USD",
    )
    make_account(
        db_session,
        connection,
        "cc-1",
        name="Card",
        type=AccountType.CREDIT_CARD,
        owner_tag=OwnerTag.JOINT,
        balance=Decimal("-50.00"),
        currency="CAD",
    )
    db_session.commit()
    user_id = user.id
    db_session.expunge_all()

    loaded = db_session.scalars(select(User).where(User.id == user_id)).one()

    assert loaded.email == "alice@example.com"
    assert loaded.password_hash == "not-a-real-hash"
    assert loaded.created_at.tzinfo is not None
    (loaded_connection,) = loaded.connections
    assert loaded_connection.user is loaded
    assert loaded_connection.provider is Provider.PLAID
    assert loaded_connection.status is ConnectionStatus.ERROR
    assert loaded_connection.encrypted_token == FAKE_TOKEN
    accounts = sorted(loaded_connection.accounts, key=lambda a: a.provider_account_id)
    assert [
        (a.provider_account_id, a.name, a.type, a.owner_tag, a.balance, a.currency)
        for a in accounts
    ] == [
        ("cc-1", "Card", AccountType.CREDIT_CARD, OwnerTag.JOINT, Decimal("-50.00"), "CAD"),
        ("chk-1", "Checking", AccountType.CHECKING, OwnerTag.MINE, Decimal("100.10"), "USD"),
    ]
    assert all(a.connection is loaded_connection for a in accounts)


def test_query_by_owner_tag_across_two_users(db_session):
    alice = make_user(db_session, "alice@example.com")
    bob = make_user(db_session, "bob@example.com")
    # A household-wide import under Alice's connection holds Bob's account as `partner`.
    alice_import = make_connection(db_session, alice, Provider.CSV)
    bob_bank = make_connection(db_session, bob, Provider.PLAID)
    make_account(db_session, alice_import, "a-mine", owner_tag=OwnerTag.MINE)
    make_account(db_session, alice_import, "a-partner", owner_tag=OwnerTag.PARTNER)
    make_account(db_session, bob_bank, "b-joint", owner_tag=OwnerTag.JOINT)
    make_account(db_session, bob_bank, "b-mine", owner_tag=OwnerTag.MINE)
    db_session.commit()

    def ids_with(tag):
        query = select(Account.provider_account_id).where(Account.owner_tag == tag)
        return sorted(db_session.scalars(query))

    assert ids_with(OwnerTag.MINE) == ["a-mine", "b-mine"]
    assert ids_with(OwnerTag.PARTNER) == ["a-partner"]
    assert ids_with(OwnerTag.JOINT) == ["b-joint"]
    alice_tags = db_session.scalars(
        select(Account.owner_tag).join(Connection).where(Connection.user_id == alice.id)
    )
    assert sorted(alice_tags) == [OwnerTag.MINE, OwnerTag.PARTNER]


def test_raw_sql_stores_lowercase_values(db_session):
    user = make_user(db_session)
    connection = make_connection(db_session, user, Provider.PLAID)
    account = make_account(
        db_session, connection, type=AccountType.CREDIT_CARD, owner_tag=OwnerTag.JOINT
    )
    db_session.commit()

    row = db_session.execute(
        text(
            "select a.type, a.owner_tag, c.provider, c.status "
            "from accounts a join connections c on c.id = a.connection_id where a.id = :id"
        ),
        {"id": account.id},
    ).one()

    assert tuple(row) == ("credit_card", "joint", "plaid", "active")


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("owner_tag", "ours"),
        ("type", "crypto"),
        ("owner_tag", "MINE"),
        ("type", "CREDIT_CARD"),
    ],
)
def test_unknown_account_enum_value_is_rejected(db_session, column, value):
    connection = make_connection(db_session, make_user(db_session))
    params = {"cid": connection.id, "type": "checking", "owner_tag": "mine", column: value}

    expect_integrity_error(
        db_session,
        "insert into accounts (connection_id, provider_account_id, name, type, owner_tag) "
        "values (:cid, 'x', 'x', :type, :owner_tag)",
        **params,
    )


@pytest.mark.parametrize(
    ("provider", "status"),
    [("mint", "active"), ("PLAID", "active"), ("plaid", "broken"), ("plaid", "ACTIVE")],
)
def test_unknown_connection_enum_value_is_rejected(db_session, provider, status):
    user = make_user(db_session)

    expect_integrity_error(
        db_session,
        "insert into connections (user_id, provider, status) values (:uid, :provider, :status)",
        uid=user.id,
        provider=provider,
        status=status,
    )


def test_duplicate_email_is_rejected(db_session):
    make_user(db_session, "alice@example.com")

    expect_integrity_error(
        db_session,
        "insert into users (email, password_hash) values ('alice@example.com', 'x')",
    )
    # The session is still usable after the failed statement, and the first row is kept.
    emails = db_session.scalars(select(User.email).where(User.email == "alice@example.com"))
    assert list(emails) == ["alice@example.com"]


def test_upper_case_email_is_rejected(db_session):
    expect_integrity_error(
        db_session,
        "insert into users (email, password_hash) values ('Alice@example.com', 'x')",
    )


def test_account_with_missing_connection_is_rejected(db_session):
    expect_integrity_error(
        db_session,
        "insert into accounts (connection_id, provider_account_id, name, type) "
        "values (-1, 'x', 'x', 'checking')",
    )


def test_connection_with_missing_user_is_rejected(db_session):
    expect_integrity_error(
        db_session,
        "insert into connections (user_id, provider) values (-1, 'seed')",
    )


def test_deleting_user_with_connection_is_restricted(db_session):
    user = make_user(db_session)
    make_connection(db_session, user)

    expect_integrity_error(db_session, "delete from users where id = :id", id=user.id)


def test_deleting_connection_with_accounts_is_restricted(db_session):
    connection = make_connection(db_session, make_user(db_session))
    make_account(db_session, connection)

    expect_integrity_error(db_session, "delete from connections where id = :id", id=connection.id)


def test_provider_account_id_unique_per_connection(db_session):
    user = make_user(db_session)
    first = make_connection(db_session, user, Provider.PLAID)
    second = make_connection(db_session, user, Provider.PLAID)
    make_account(db_session, first, "same-id")

    expect_integrity_error(
        db_session,
        "insert into accounts (connection_id, provider_account_id, name, type) "
        "values (:cid, 'same-id', 'x', 'checking')",
        cid=first.id,
    )

    make_account(db_session, second, "same-id")
    db_session.commit()
    connection_ids = db_session.scalars(
        select(Account.connection_id).where(Account.provider_account_id == "same-id")
    )
    assert sorted(connection_ids) == sorted([first.id, second.id])


def test_encrypted_token_null_and_bytes_round_trip(db_session):
    user = make_user(db_session)
    without = make_connection(db_session, user, Provider.MONARCH)
    with_token = make_connection(db_session, user, Provider.PLAID, encrypted_token=FAKE_TOKEN)
    db_session.commit()
    ids = {"without": without.id, "with": with_token.id}
    db_session.expunge_all()

    tokens = dict(
        db_session.execute(
            select(Connection.id, Connection.encrypted_token).where(Connection.id.in_(ids.values()))
        ).all()
    )

    assert tokens == {ids["without"]: None, ids["with"]: FAKE_TOKEN}


def test_balance_round_trips_exactly_and_defaults_come_from_database(db_session):
    user_id = db_session.execute(
        text(
            "insert into users (email, password_hash) "
            "values ('defaults@example.com', 'x') returning id"
        )
    ).scalar_one()
    connection_id = db_session.execute(
        text("insert into connections (user_id, provider) values (:uid, 'seed') returning id"),
        {"uid": user_id},
    ).scalar_one()
    db_session.execute(
        text(
            "insert into accounts (connection_id, provider_account_id, name, type, balance) "
            "values (:cid, 'no-balance', 'x', 'savings', null), "
            "(:cid, 'negative', 'x', 'loan', :balance)"
        ),
        {"cid": connection_id, "balance": Decimal("-1234.56")},
    )
    db_session.commit()

    accounts = {
        a.provider_account_id: a
        for a in db_session.scalars(select(Account).where(Account.connection_id == connection_id))
    }
    connection = db_session.get(Connection, connection_id)
    user = db_session.get(User, user_id)

    assert accounts["no-balance"].balance is None
    assert accounts["negative"].balance == Decimal("-1234.56")
    assert str(accounts["negative"].balance) == "-1234.56"
    assert all(a.owner_tag is OwnerTag.MINE for a in accounts.values())
    assert all(a.currency == "USD" for a in accounts.values())
    assert all(a.created_at is not None for a in accounts.values())
    assert connection.status is ConnectionStatus.ACTIVE
    assert connection.created_at is not None
    assert user.created_at is not None
