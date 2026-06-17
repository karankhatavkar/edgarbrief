import asyncio
import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from supabase_auth.errors import AuthApiError

from app.auth import dependencies
from app.auth.dependencies import CurrentUser, get_current_user


def _call(credentials):
    return asyncio.run(get_current_user(credentials))


def _bearer(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _stub_anon_client(monkeypatch, *, user=None, error=None):
    async def get_user(token):
        if error is not None:
            raise error
        return SimpleNamespace(user=user) if user is not None else None

    client = SimpleNamespace(auth=SimpleNamespace(get_user=get_user))

    async def anon_client():
        return client

    monkeypatch.setattr(dependencies, "anon_client", anon_client)


def test_missing_credentials_rejected():
    with pytest.raises(HTTPException) as exc:
        _call(None)
    assert exc.value.status_code == 401
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


def test_invalid_or_expired_token_rejected(monkeypatch):
    _stub_anon_client(monkeypatch, error=AuthApiError("expired", 401, "bad_jwt"))
    with pytest.raises(HTTPException) as exc:
        _call(_bearer("expired.jwt"))
    assert exc.value.status_code == 401


def test_no_user_in_response_rejected(monkeypatch):
    _stub_anon_client(monkeypatch, user=None)
    with pytest.raises(HTTPException) as exc:
        _call(_bearer("unknown.jwt"))
    assert exc.value.status_code == 401


def test_valid_token_returns_current_user(monkeypatch):
    user_id = uuid.uuid4()
    user = SimpleNamespace(id=str(user_id), email="caller@example.com")
    _stub_anon_client(monkeypatch, user=user)

    result = _call(_bearer("good.jwt"))

    assert result == CurrentUser(
        id=user_id, email="caller@example.com", access_token="good.jwt"
    )
