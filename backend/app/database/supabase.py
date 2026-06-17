"""Supabase client construction.

Two flavors, picked by who is making the call:

- ``service_client()`` uses the service-role key and **bypasses RLS**. Use it for
  trusted server-side work only (ingestion, saving assistant messages). Never
  hand it a path that mixes in unvalidated user input.
- ``user_client(access_token)`` uses the anon key carrying the caller's JWT, so
  every query runs under that user's row-level-security policies.

Both return the async client; request-path code must not block the event loop.
"""

import asyncio

from supabase import AsyncClient, create_async_client
from supabase.lib.client_options import AsyncClientOptions

from app.config import settings

# Server-side clients hold no browser session: don't persist or refresh tokens.
_SERVER_OPTIONS = AsyncClientOptions(auto_refresh_token=False, persist_session=False)

_service_client: AsyncClient | None = None
_service_lock = asyncio.Lock()

_anon_client: AsyncClient | None = None
_anon_lock = asyncio.Lock()


async def anon_client() -> AsyncClient:
    """Return the shared anon-key client, creating it on first use.

    Carries no caller JWT, so it runs under RLS as the anonymous role. Used to
    verify caller tokens via ``auth.get_user`` — pass the token to that call
    rather than binding it to this shared client.
    """
    global _anon_client
    if _anon_client is None:
        async with _anon_lock:
            if _anon_client is None:
                _anon_client = await create_async_client(
                    settings.supabase_url,
                    settings.supabase_anon_key,
                    options=_SERVER_OPTIONS,
                )
    return _anon_client


async def service_client() -> AsyncClient:
    """Return the shared service-role client, creating it on first use.

    Bypasses RLS — keep it away from user-controlled query paths.
    """
    global _service_client
    if _service_client is None:
        async with _service_lock:
            if _service_client is None:
                _service_client = await create_async_client(
                    settings.supabase_url,
                    settings.supabase_service_role_key,
                    options=_SERVER_OPTIONS,
                )
    return _service_client


async def user_client(access_token: str) -> AsyncClient:
    """Build an anon-key client scoped to ``access_token`` so RLS applies as that user.

    Created fresh per caller — the token is request-specific and must not leak
    across users.
    """
    client = await create_async_client(
        settings.supabase_url,
        settings.supabase_anon_key,
        options=_SERVER_OPTIONS,
    )
    client.postgrest.auth(access_token)
    return client
