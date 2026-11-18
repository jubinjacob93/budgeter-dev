from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budgeter.core.models.base import Base
from budgeter.core.models.enums import AccountType, OwnerTag, string_enum

if TYPE_CHECKING:
    from budgeter.core.models.connection import Connection


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        # Re-importing the same provider account updates it instead of adding a duplicate.
        UniqueConstraint("connection_id", "provider_account_id"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("connections.id", ondelete="RESTRICT"), index=True
    )
    provider_account_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[AccountType] = mapped_column(string_enum(AccountType, "type"))
    # Relative to the connection's user: `partner` is the other household member's account.
    owner_tag: Mapped[OwnerTag] = mapped_column(
        string_enum(OwnerTag, "owner_tag"), server_default=OwnerTag.MINE.value
    )
    # As the provider reports it; NULL until the first sync.
    balance: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(CHAR(3), server_default="USD")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    connection: Mapped["Connection"] = relationship(back_populates="accounts")

    def __repr__(self) -> str:
        return (
            f"Account(id={self.id!r}, connection_id={self.connection_id!r}, "
            f"name={self.name!r}, type={self.type!r}, owner_tag={self.owner_tag!r})"
        )
