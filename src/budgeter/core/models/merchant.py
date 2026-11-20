from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budgeter.core.models.base import Base

if TYPE_CHECKING:
    from budgeter.core.models.transaction import Transaction


class Merchant(Base):
    """A normalized merchant. The pgvector `embedding` column is added in task 28."""

    __tablename__ = "merchants"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # Case-sensitive: producing one consistent spelling is the normalizer's job.
    normalized_name: Mapped[str] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="merchant")

    def __repr__(self) -> str:
        return f"Merchant(id={self.id!r}, normalized_name={self.normalized_name!r})"
