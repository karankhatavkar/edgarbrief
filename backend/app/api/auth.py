"""Auth-related routes.

``GET /me`` is the first endpoint behind ``get_current_user``: it does no work
beyond echoing the verified caller back, which makes it the natural smoke test
that a frontend token is reaching the backend and passing verification.
"""

import uuid

from fastapi import APIRouter
from pydantic import BaseModel

from app.auth.dependencies import CurrentUserDep

router = APIRouter(tags=["auth"])


class Me(BaseModel):
    id: uuid.UUID
    email: str | None


@router.get("/me")
async def me(user: CurrentUserDep) -> Me:
    return Me(id=user.id, email=user.email)
