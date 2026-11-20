import datetime as dt
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budgeter.core.models.base import Base
from budgeter.core.models.enums import Provider, string_enum

if TYPE_CHECKING:
    from budgeter.core.models.account import Account
    from budgeter.core.models.category import Category
    from budgeter.core.models.merchant import Merchant
    from budgeter.core.models.transaction_split import TransactionSplit


class Transaction(Base):
    """A normalized transaction.

    `amount` is signed: negative means money leaves the account (purchases, fees, payments
    out), positive means money comes in (income, refunds, transfers in). Every provider
    converts to this convention.
    """

    __tablename__ = "transactions"
    __table_args__ = (
        # Deduplication key across all accounts. Named uq_transactions_provider by the
        # convention (first column only).
        UniqueConstraint("provider", "provider_txn_id"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), index=True
    )
    # Copied from the account's connection by the ingestion pipeline; not enforced here.
    provider: Mapped[Provider] = mapped_column(string_enum(Provider, "provider"))
    provider_txn_id: Mapped[str] = mapped_column(String(255))
    date: Mapped[dt.date] = mapped_column(Date, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    # The provider's description as received.
    merchant_raw: Mapped[str] = mapped_column(String(500))
    merchant_id: Mapped[int | None] = mapped_column(
        ForeignKey("merchants.id", ondelete="RESTRICT"), index=True
    )
    # NULL means uncategorized.
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    is_transfer: Mapped[bool] = mapped_column(Boolean, server_default=false())
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    account: Mapped["Account"] = relationship(back_populates="transactions")
    merchant: Mapped["Merchant | None"] = relationship(back_populates="transactions")
    category: Mapped["Category | None"] = relationship(back_populates="transactions")
    splits: Mapped[list["TransactionSplit"]] = relationship(back_populates="transaction")

    def __repr__(self) -> str:
        # Never include notes: they are free text a person wrote.
        return (
            f"Transaction(id={self.id!r}, account_id={self.account_id!r}, "
            f"provider={self.provider!r}, provider_txn_id={self.provider_txn_id!r}, "
            f"date={self.date!r}, amount={self.amount!r})"
        )
