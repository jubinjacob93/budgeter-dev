from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Identity, LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from budgeter.core.models.base import Base
from budgeter.core.models.enums import ConnectionStatus, Provider, string_enum

if TYPE_CHECKING:
    from budgeter.core.models.account import Account
    from budgeter.core.models.user import User


class Connection(Base):
    """One institution login, or one seed / CSV / Monarch import (those have no token)."""

    __tablename__ = "connections"

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    provider: Mapped[Provider] = mapped_column(string_enum(Provider, "provider"))
    encrypted_token: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[ConnectionStatus] = mapped_column(
        string_enum(ConnectionStatus, "status"), server_default=ConnectionStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="connections")
    accounts: Mapped[list["Account"]] = relationship(back_populates="connection")

    def __repr__(self) -> str:
        # Never include encrypted_token, so it cannot end up in logs or tracebacks.
        return (
            f"Connection(id={self.id!r}, user_id={self.user_id!r}, "
            f"provider={self.provider!r}, status={self.status!r})"
        )
