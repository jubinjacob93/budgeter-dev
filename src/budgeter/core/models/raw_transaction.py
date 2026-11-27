from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Identity, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from budgeter.core.models.base import Base
from budgeter.core.models.enums import Provider, string_enum


class RawTransaction(Base):
    """A provider's transaction payload exactly as received, so any sync can be replayed."""

    __tablename__ = "raw_transactions"
    __table_args__ = (
        # Re-importing the same payload updates it instead of adding a row. Named
        # uq_raw_transactions_provider by the convention (first column only).
        UniqueConstraint("provider", "provider_txn_id"),
    )

    id: Mapped[int] = mapped_column(Identity(), primary_key=True)
    # The login the payload came from.
    connection_id: Mapped[int] = mapped_column(
        ForeignKey("connections.id", ondelete="RESTRICT"), index=True
    )
    provider: Mapped[Provider] = mapped_column(string_enum(Provider, "provider"))
    provider_txn_id: Mapped[str] = mapped_column(String(255))
    payload: Mapped[Any] = mapped_column(JSONB, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self) -> str:
        # Never include payload: it is raw bank data.
        return (
            f"RawTransaction(id={self.id!r}, connection_id={self.connection_id!r}, "
            f"provider={self.provider!r}, provider_txn_id={self.provider_txn_id!r})"
        )
