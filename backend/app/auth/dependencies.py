"""Authentication boundary.

Every chat or retrieval request must arrive with ``Authorization: Bearer
<supabase_jwt>``. ``get_current_user`` verifies that token against Supabase Auth
and returns the caller; missing, malformed, or expired tokens are rejected with
``401`` before any downstream work runs.
"""

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase_auth.errors import AuthError

from app.database.supabase import anon_client

# auto_error=False so we raise our own 401 (with WWW-Authenticate) uniformly,
# whether the header is absent or the token is bad.
_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """The authenticated caller, resolved from a verified Supabase JWT."""

    id: uuid.UUID
    email: str | None
    access_token: str


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing or invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> CurrentUser:
    """Verify the bearer token with Supabase Auth and return the caller.

    Supabase ``get_user`` validates the signature and expiry server-side, so we
    don't re-implement JWT verification here.
    """
    if credentials is None:
        raise _unauthorized()

    token = credentials.credentials
    client = await anon_client()
    try:
        response = await client.auth.get_user(token)
    except AuthError:
        raise _unauthorized() from None

    if response is None:
        raise _unauthorized()

    user = response.user
    return CurrentUser(id=uuid.UUID(user.id), email=user.email, access_token=token)


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
