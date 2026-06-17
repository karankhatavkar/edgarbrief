"""Chat thread CRUD routes.

GET  /threads               — list threads for the authenticated user
POST /threads               — create a new thread
GET  /threads/{id}/messages — load message history (403 if not owner)
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict

from app.api.deps import UserClientDep, require_owned_thread
from app.auth.dependencies import CurrentUserDep
from app.database import threads as thread_db
from app.database.supabase import service_client

router = APIRouter(prefix="/threads", tags=["chat"])


class ThreadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    thread_id: uuid.UUID
    role: str
    content: str
    created_at: datetime


class CreateThreadIn(BaseModel):
    title: str = "New Chat"


@router.get("", response_model=list[ThreadOut])
async def list_threads(client: UserClientDep) -> list[ThreadOut]:
    rows = await thread_db.list_threads(client)
    return [ThreadOut.model_validate(r) for r in rows]


@router.post("", response_model=ThreadOut, status_code=status.HTTP_201_CREATED)
async def create_thread(
    body: CreateThreadIn, user: CurrentUserDep, client: UserClientDep
) -> ThreadOut:
    # The users row must exist for the chat_threads FK; only the service-role
    # client may insert it (RLS lets users select/update their own row, not
    # insert). The thread itself is created under the caller's RLS scope.
    svc = await service_client()
    await thread_db.ensure_user(svc, user.id, user.email)

    row = await thread_db.create_thread(client, user.id, body.title)
    return ThreadOut.model_validate(row)


@router.get("/{thread_id}/messages", response_model=list[MessageOut])
async def get_messages(thread_id: uuid.UUID, client: UserClientDep) -> list[MessageOut]:
    await require_owned_thread(client, thread_id)
    rows = await thread_db.list_messages(client, thread_id)
    return [MessageOut.model_validate(r) for r in rows]
