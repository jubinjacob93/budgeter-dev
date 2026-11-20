"""create transaction category tables

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-19 21:13:46.650369

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Referenced tables first: categories and merchants before transactions, transactions
    # before transaction_splits. `provider` is VARCHAR with a named CHECK constraint
    # (native_enum=False), so no Postgres ENUM type is created.
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("group_name", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
        sa.UniqueConstraint("name", name=op.f("uq_categories_name")),
    )
    op.create_table(
        "merchants",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("normalized_name", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_merchants")),
        sa.UniqueConstraint("normalized_name", name=op.f("uq_merchants_normalized_name")),
    )
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("pattern", sa.String(length=255), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_category_rules_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_rules")),
        sa.UniqueConstraint("pattern", name=op.f("uq_category_rules_pattern")),
    )
    op.create_index(
        op.f("ix_category_rules_category_id"), "category_rules", ["category_id"], unique=False
    )
    op.create_table(
        "raw_transactions",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "seed",
                "csv",
                "monarch",
                "plaid",
                "simplefin",
                name="provider",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("provider_txn_id", sa.String(length=255), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            name=op.f("fk_raw_transactions_connection_id_connections"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_raw_transactions")),
        sa.UniqueConstraint(
            "provider", "provider_txn_id", name=op.f("uq_raw_transactions_provider")
        ),
    )
    op.create_index(
        op.f("ix_raw_transactions_connection_id"),
        "raw_transactions",
        ["connection_id"],
        unique=False,
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum(
                "seed",
                "csv",
                "monarch",
                "plaid",
                "simplefin",
                name="provider",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column("provider_txn_id", sa.String(length=255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("merchant_raw", sa.String(length=500), nullable=False),
        sa.Column("merchant_id", sa.Integer(), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("is_transfer", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["account_id"],
            ["accounts.id"],
            name=op.f("fk_transactions_account_id_accounts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_transactions_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["merchant_id"],
            ["merchants.id"],
            name=op.f("fk_transactions_merchant_id_merchants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint("provider", "provider_txn_id", name=op.f("uq_transactions_provider")),
    )
    op.create_index(
        op.f("ix_transactions_account_id"), "transactions", ["account_id"], unique=False
    )
    op.create_index(
        op.f("ix_transactions_category_id"), "transactions", ["category_id"], unique=False
    )
    op.create_index(op.f("ix_transactions_date"), "transactions", ["date"], unique=False)
    op.create_index(
        op.f("ix_transactions_merchant_id"), "transactions", ["merchant_id"], unique=False
    )
    op.create_table(
        "transaction_splits",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("transaction_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_transaction_splits_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_transaction_splits_transaction_id_transactions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transaction_splits")),
    )
    op.create_index(
        op.f("ix_transaction_splits_category_id"),
        "transaction_splits",
        ["category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_transaction_splits_transaction_id"),
        "transaction_splits",
        ["transaction_id"],
        unique=False,
    )


def downgrade() -> None:
    # Reverse dependency order. users, connections, accounts and the vector extension stay.
    op.drop_index(op.f("ix_transaction_splits_transaction_id"), table_name="transaction_splits")
    op.drop_index(op.f("ix_transaction_splits_category_id"), table_name="transaction_splits")
    op.drop_table("transaction_splits")
    op.drop_index(op.f("ix_transactions_merchant_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_date"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_category_id"), table_name="transactions")
    op.drop_index(op.f("ix_transactions_account_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_raw_transactions_connection_id"), table_name="raw_transactions")
    op.drop_table("raw_transactions")
    op.drop_index(op.f("ix_category_rules_category_id"), table_name="category_rules")
    op.drop_table("category_rules")
    op.drop_table("merchants")
    op.drop_table("categories")
