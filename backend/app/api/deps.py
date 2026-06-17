"""Shared FastAPI dependencies for the API layer.

Composes the auth boundary with the database clients so routers stay thin:
``UserClientDep`` hands a route an RLS-scoped Supabase client (and closes it),
and ``require_owned_thread`` is the single place the thread-ownership 403 lives.
"""

import uuid
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from supabase import AsyncClient

from app.auth.dependencies import CurrentUserDep
from app.database import threads as thread_db
from app.database.supabase import user_client


async def get_user_client(user: CurrentUserDep) -> AsyncGenerator[AsyncClient, None]:
    """Yield a request-scoped, RLS-bound Supabase client and close it after.

    The client must be built per request because it carries the caller's JWT.
    Closing the postgrest pool in ``finally`` keeps the underlying httpx
    connections from leaking across requests — ``.table()`` is the only API we
    use on this client, so that's the only pool opened.
    """
    client = await user_client(user.access_token)
    try:
        yield client
    finally:
        await client.postgrest.aclose()


UserClientDep = Annotated[AsyncClient, Depends(get_user_client)]


async def require_owned_thread(
    client: AsyncClient, thread_id: uuid.UUID
) -> thread_db.ThreadRow:
    """Return the thread, or raise 403 if the caller can't see it.

    RLS returns nothing for threads the caller doesn't own, so a missing row
    covers both "thread not found" and "thread belongs to another user".
    Not a FastAPI dependency because ``thread_id`` arrives from the path in one
    route and the request body in another; both call this directly.
    """
    thread = await thread_db.get_thread(client, thread_id)
    if thread is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Thread not found or access denied",
        )
    return thread
