"""Demo cost controls — enforced before a chat turn, recorded after.

Two limits keep Gemini spend bounded on the public demo:

- **Per-user lifetime budget:** each user may spend up to
  ``demo_user_token_limit`` tokens *ever* (never resets). Exhausting it is
  permanent.
- **Global monthly cap:** at most ``demo_monthly_limit`` distinct users may be
  active in a calendar month. The count is scoped to the current month, so it
  resets for free on the 1st.

The DB is touched about twice per turn, never per internal step: a pre-flight
read (+ a slot claim for a user's first turn of the month), then a single
increment after the turn. Tokens are summed across every internal step of a turn
(retries + tool calls) in memory via pydantic-ai's ``RunUsage`` and written once.
This module uses the direct async SQLAlchemy engine (table owner connection), so
it bypasses RLS on ``demo_usage``.
"""

import uuid
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.models import DemoIpUsage, DemoUsage
from app.database.session import async_session

_USER_EXHAUSTED = (
    "You've used up this demo trial. If you enjoyed it and want to see more, "
    "reach out to Karan at work.karankh@gmail.com."
)
_GLOBAL_EXHAUSTED = (
    "The demo is at capacity right now and temporarily unavailable. "
    "Please contact Karan at work.karankh@gmail.com."
)
_IP_EXHAUSTED = (
    "This demo has already been tried several times from your network. "
    "Reach out to Karan at work.karankh@gmail.com to see more."
)


class QuotaExceeded(Exception):
    """A turn is blocked: the user is out of budget, or the month is full.

    ``code`` distinguishes the two cases for the frontend; ``message`` is the
    user-facing copy.
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _current_month() -> date:
    return date.today().replace(day=1)


async def enforce_quota(
    user_id: uuid.UUID, email: str | None, ip: str | None
) -> None:
    """Raise ``QuotaExceeded`` if the user is out of budget or a cap is full.

    For a user not yet active this month, claims their monthly demo slot up front
    (and bumps the per-IP counter when ``ip`` is known) so a burst of new users —
    or fresh anonymous identities minted from one machine — can't overshoot the
    caps. A missing/unparseable ``ip`` skips only the IP brake (fail-open: never
    block a real user because we couldn't read their IP). Exempt emails bypass
    every check (the owner, for testing).
    """
    if email is not None and email in settings.demo_exempt_emails:
        return

    month = _current_month()
    async with async_session() as session:
        row = await session.get(DemoUsage, user_id)

        if row is not None and row.total_tokens >= settings.demo_user_token_limit:
            raise QuotaExceeded("user_quota_exhausted", _USER_EXHAUSTED)

        already_active_this_month = row is not None and row.last_active_month == month
        if not already_active_this_month:
            active = await session.scalar(
                select(func.count())
                .select_from(DemoUsage)
                .where(DemoUsage.last_active_month == month)
            )
            if (active or 0) >= settings.demo_monthly_limit:
                raise QuotaExceeded("global_quota_exhausted", _GLOBAL_EXHAUSTED)

            if ip is not None:
                ip_count = await session.scalar(
                    select(DemoIpUsage.user_count).where(
                        DemoIpUsage.ip == ip, DemoIpUsage.month == month
                    )
                )
                if (ip_count or 0) >= settings.demo_ip_monthly_limit:
                    raise QuotaExceeded("ip_quota_exhausted", _IP_EXHAUSTED)

            await _claim_month(session, user_id, month)
            if ip is not None:
                await _bump_ip(session, ip, month)
            await session.commit()


async def record_usage(user_id: uuid.UUID, tokens: int, requests: int) -> None:
    """Add a completed turn's token + request cost to the user's lifetime total.

    One upsert per turn — ``tokens`` is the whole turn's usage already summed
    across retries and tool calls.
    """
    month = _current_month()
    async with async_session() as session:
        await session.execute(
            insert(DemoUsage)
            .values(
                user_id=user_id,
                total_tokens=tokens,
                total_requests=requests,
                last_active_month=month,
            )
            .on_conflict_do_update(
                index_elements=["user_id"],
                set_={
                    "total_tokens": DemoUsage.total_tokens + tokens,
                    "total_requests": DemoUsage.total_requests + requests,
                    "last_active_month": month,
                    "updated_at": func.now(),
                },
            )
        )
        await session.commit()


async def _claim_month(
    session: AsyncSession, user_id: uuid.UUID, month: date
) -> None:
    """Mark the user active this month (no token change) to claim a demo slot."""
    await session.execute(
        insert(DemoUsage)
        .values(
            user_id=user_id, total_tokens=0, total_requests=0, last_active_month=month
        )
        .on_conflict_do_update(
            index_elements=["user_id"],
            set_={"last_active_month": month, "updated_at": func.now()},
        )
    )


async def _bump_ip(session: AsyncSession, ip: str, month: date) -> None:
    """Count one more distinct demo user started from ``ip`` this month."""
    await session.execute(
        insert(DemoIpUsage)
        .values(ip=ip, month=month, user_count=1)
        .on_conflict_do_update(
            index_elements=["ip", "month"],
            set_={
                "user_count": DemoIpUsage.user_count + 1,
                "updated_at": func.now(),
            },
        )
    )
