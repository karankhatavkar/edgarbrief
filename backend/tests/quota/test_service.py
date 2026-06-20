"""Unit tests for demo cost controls — no DB, no network.

The async SQLAlchemy session is replaced with an in-memory fake and the limit
settings are monkeypatched, so ``enforce_quota`` / ``record_usage`` run in
isolation. We assert on control flow (raise vs. allow) and on whether a write
(slot claim / ip bump / usage upsert) was issued — not on SQL text.
"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest

from app.quota import service
from app.quota.service import QuotaExceeded


class _FakeSession:
    """Stand-in for an async SQLAlchemy session and its context manager.

    ``scalar`` answers the two count queries in the order ``enforce_quota`` issues
    them: the global monthly count first, then the per-IP count.
    """

    def __init__(self, *, row=None, active_count=0, ip_count=0):
        self._row = row
        self._active_count = active_count
        self._ip_count = ip_count
        self._scalar_calls = 0
        self.executed: list = []
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, model, pk):
        return self._row

    async def scalar(self, stmt):
        self._scalar_calls += 1
        return self._active_count if self._scalar_calls == 1 else self._ip_count

    async def execute(self, stmt):
        self.executed.append(stmt)

    async def commit(self):
        self.committed = True


def _use_session(monkeypatch, session: _FakeSession) -> None:
    monkeypatch.setattr(service, "async_session", lambda: session)


def _set_limits(monkeypatch, *, tokens=1000, monthly=20, ip=5, exempt=()) -> None:
    monkeypatch.setattr(service.settings, "demo_user_token_limit", tokens)
    monkeypatch.setattr(service.settings, "demo_monthly_limit", monthly)
    monkeypatch.setattr(service.settings, "demo_ip_monthly_limit", ip)
    monkeypatch.setattr(service.settings, "demo_exempt_emails", list(exempt))


def _run(coro):
    return asyncio.run(coro)


def test_exempt_email_bypasses_without_touching_db(monkeypatch):
    _set_limits(monkeypatch, exempt=["owner@example.com"])

    def explode():
        raise AssertionError("async_session must not open for an exempt user")

    monkeypatch.setattr(service, "async_session", explode)

    _run(service.enforce_quota(uuid.uuid4(), "owner@example.com", "1.2.3.4"))


def test_user_over_lifetime_limit_raises(monkeypatch):
    _set_limits(monkeypatch, tokens=1000)
    row = SimpleNamespace(total_tokens=1000, last_active_month=service._current_month())
    _use_session(monkeypatch, _FakeSession(row=row))

    with pytest.raises(QuotaExceeded) as exc:
        _run(service.enforce_quota(uuid.uuid4(), "user@example.com", None))
    assert exc.value.code == "user_quota_exhausted"


def test_month_full_new_user_raises_and_claims_nothing(monkeypatch):
    _set_limits(monkeypatch, monthly=20)
    # Brand-new user (no row) arriving when the month is already at capacity.
    session = _FakeSession(row=None, active_count=20)
    _use_session(monkeypatch, session)

    with pytest.raises(QuotaExceeded) as exc:
        _run(service.enforce_quota(uuid.uuid4(), "new@example.com", "1.2.3.4"))
    assert exc.value.code == "global_quota_exhausted"
    assert session.executed == []  # rejected -> no slot claimed


def test_new_user_under_limits_claims_a_slot(monkeypatch):
    _set_limits(monkeypatch, tokens=1000, monthly=20)
    session = _FakeSession(row=None, active_count=5)
    _use_session(monkeypatch, session)

    _run(service.enforce_quota(uuid.uuid4(), "new@example.com", None))  # no raise

    assert len(session.executed) == 1  # claimed this month's demo slot, no ip bump
    assert session.committed is True


def test_returning_user_this_month_allowed_even_when_full(monkeypatch):
    _set_limits(monkeypatch, tokens=1000, monthly=20)
    # Already counted this month and under budget: skip the count, claim nothing.
    row = SimpleNamespace(total_tokens=10, last_active_month=service._current_month())
    session = _FakeSession(row=row, active_count=999, ip_count=999)
    _use_session(monkeypatch, session)

    _run(service.enforce_quota(uuid.uuid4(), "returning@example.com", "1.2.3.4"))

    assert session.executed == []  # slot already held; nothing written


def test_ip_over_limit_raises_and_claims_nothing(monkeypatch):
    _set_limits(monkeypatch, monthly=20, ip=5)
    # New user, month has room, but this IP already started 5 users this month.
    session = _FakeSession(row=None, active_count=1, ip_count=5)
    _use_session(monkeypatch, session)

    with pytest.raises(QuotaExceeded) as exc:
        _run(service.enforce_quota(uuid.uuid4(), "new@example.com", "1.2.3.4"))
    assert exc.value.code == "ip_quota_exhausted"
    assert session.executed == []  # rejected before claim/bump
    assert session.committed is False


def test_new_user_under_ip_limit_claims_slot_and_bumps_ip(monkeypatch):
    _set_limits(monkeypatch, monthly=20, ip=5)
    session = _FakeSession(row=None, active_count=1, ip_count=2)
    _use_session(monkeypatch, session)

    _run(service.enforce_quota(uuid.uuid4(), "new@example.com", "1.2.3.4"))

    assert len(session.executed) == 2  # claim slot + bump ip
    assert session.committed is True


def test_missing_ip_skips_ip_brake(monkeypatch):
    # IP unknown (fail-open): a full IP must not block, and no ip query/bump runs.
    _set_limits(monkeypatch, monthly=20, ip=1)
    session = _FakeSession(row=None, active_count=1, ip_count=999)
    _use_session(monkeypatch, session)

    _run(service.enforce_quota(uuid.uuid4(), "new@example.com", None))  # no raise

    assert len(session.executed) == 1  # only the slot claim, no ip bump
    assert session.committed is True


def test_record_usage_upserts_once_and_commits(monkeypatch):
    session = _FakeSession()
    _use_session(monkeypatch, session)

    _run(service.record_usage(uuid.uuid4(), tokens=1234, requests=3))

    assert len(session.executed) == 1  # one upsert per turn
    assert session.committed is True
