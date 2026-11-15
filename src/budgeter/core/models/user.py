from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, Identity, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budgeter.core.models.base import Base

if TYPE_CHECKING:
    from budgeter.core.models.connection import Connection


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        # Together with the unique constraint this makes emails unique regardless of case.
        CheckConstraint("email = lower(email)", name="email_lowercase"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    connections: Mapped[list["Connection"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, email={self.email!r})"
