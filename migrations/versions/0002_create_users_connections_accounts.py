"""create users connections accounts

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-14 23:44:35.434364

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enum columns are VARCHAR with a named CHECK constraint (native_enum=False), so no
    # Postgres ENUM type is created and downgrade has none to drop.
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "connections",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
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
        sa.Column("encrypted_token", sa.LargeBinary(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "login_required",
                "error",
                "disconnected",
                name="status",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="active",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_connections_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_connections")),
    )
    op.create_index(op.f("ix_connections_user_id"), "connections", ["user_id"], unique=False)
    op.create_table(
        "accounts",
        sa.Column("id", sa.Integer(), sa.Identity(always=False), nullable=False),
        sa.Column("connection_id", sa.Integer(), nullable=False),
        sa.Column("provider_account_id", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "checking",
                "savings",
                "credit_card",
                "brokerage",
                "retirement",
                "loan",
                "other",
                name="type",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "owner_tag",
            sa.Enum(
                "mine",
                "partner",
                "joint",
                name="owner_tag",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="mine",
            nullable=False,
        ),
        sa.Column("balance", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("currency", sa.CHAR(length=3), server_default="USD", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["connection_id"],
            ["connections.id"],
            name=op.f("fk_accounts_connection_id_connections"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_accounts")),
        sa.UniqueConstraint(
            "connection_id", "provider_account_id", name=op.f("uq_accounts_connection_id")
        ),
    )
    op.create_index(op.f("ix_accounts_connection_id"), "accounts", ["connection_id"], unique=False)


def downgrade() -> None:
    # Reverse dependency order. The vector extension from 0001 stays.
    op.drop_index(op.f("ix_accounts_connection_id"), table_name="accounts")
    op.drop_table("accounts")
    op.drop_index(op.f("ix_connections_user_id"), table_name="connections")
    op.drop_table("connections")
    op.drop_table("users")
