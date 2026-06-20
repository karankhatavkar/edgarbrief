"""`demo_ip_usage` — per-IP monthly count of distinct demo users started.

A *soft, additive* abuse brake that sits beside the per-user lifetime budget and
the global monthly cap. Because an anonymous Supabase identity is free to mint
(clear localStorage / incognito → a fresh user_id → a fresh per-user budget),
nothing durable ties a returning visitor to their spent quota. This table counts
how many distinct demo users one client IP has *started* in a calendar month, so
a single machine can't farm unlimited fresh budgets.

Grain is (ip, month), so the count resets for free on the 1st. Server-managed:
the backend connects as table owner and bypasses the deny-all RLS policy.
"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.models.base import Base


class DemoIpUsage(Base):
    """How many distinct demo users one IP has started in a given month."""

    __tablename__ = "demo_ip_usage"

    # 45 chars holds a full IPv6 literal; IPv6 is stored as its /64 prefix (see
    # quota.client_ip) so a single host can't rotate within its allocation.
    ip: Mapped[str] = mapped_column(String(45), primary_key=True)
    month: Mapped[date] = mapped_column(Date, primary_key=True)
    user_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
