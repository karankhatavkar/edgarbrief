"""`demo_usage` — per-user demo token accounting + monthly demo slotting."""

import uuid
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class DemoUsage(Base):
    """Lifetime token spend per user, plus the month they were last active.

    `total_tokens` is a lifetime budget that never resets — an exhausted user is
    permanently done. The global "N demos/month" cap is enforced by counting
    distinct users whose `last_active_month` is the current month, so it resets
    for free each calendar month. Server-managed: the backend connects as table
    owner and bypasses the deny-all RLS policy; no API client touches this table.
    """

    __tablename__ = "demo_usage"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    total_tokens: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    total_requests: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    last_active_month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
