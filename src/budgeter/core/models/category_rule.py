from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budgeter.core.models.base import Base

if TYPE_CHECKING:
    from budgeter.core.models.category import Category


class CategoryRule(Base):
    """Pattern -> category, evaluated before the LLM. How patterns match is task 13."""

    __tablename__ = "category_rules"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # Unique, so one pattern cannot point to two categories.
    pattern: Mapped[str] = mapped_column(String(255), unique=True)
    category_id: Mapped[int] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    category: Mapped["Category"] = relationship(back_populates="rules")

    def __repr__(self) -> str:
        return (
            f"CategoryRule(id={self.id!r}, pattern={self.pattern!r}, "
            f"category_id={self.category_id!r})"
        )
