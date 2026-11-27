from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Identity, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budgeter.core.models.base import Base

if TYPE_CHECKING:
    from budgeter.core.models.category import Category
    from budgeter.core.models.transaction import Transaction


class TransactionSplit(Base):
    """Part of a transaction's amount assigned to a category, with the parent's sign."""

    __tablename__ = "transaction_splits"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    transaction_id: Mapped[int] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), index=True
    )
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))

    transaction: Mapped["Transaction"] = relationship(back_populates="splits")
    category: Mapped["Category"] = relationship()

    def __repr__(self) -> str:
        return (
            f"TransactionSplit(id={self.id!r}, transaction_id={self.transaction_id!r}, "
            f"category_id={self.category_id!r}, amount={self.amount!r})"
        )
