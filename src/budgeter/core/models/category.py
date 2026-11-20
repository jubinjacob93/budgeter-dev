from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budgeter.core.models.base import Base

if TYPE_CHECKING:
    from budgeter.core.models.category_rule import CategoryRule
    from budgeter.core.models.transaction import Transaction


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    # The plan's `group`, renamed because GROUP is a reserved word in SQL.
    group_name: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="category")
    rules: Mapped[list["CategoryRule"]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"Category(id={self.id!r}, name={self.name!r}, group_name={self.group_name!r})"
