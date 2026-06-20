"""Chat streaming route.

POST /chat/stream — AI SDK data-stream of one assistant turn (stub in Phase 3).
"""

import uuid

import structlog
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import UserClientDep, require_owned_thread
from app.auth.dependencies import CurrentUserDep
from app.chat.orchestrator import run_chat_turn
from app.chat.streaming import DATA_STREAM_HEADERS
from app.database import threads as thread_db
from app.database.supabase import service_client
from app.quota import QuotaExceeded, enforce_quota
from app.quota.client_ip import client_ip

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageIn(BaseModel):
    role: str
    content: str


class StreamRequest(BaseModel):
    thread_id: uuid.UUID
    messages: list[ChatMessageIn]


@router.post("/stream")
async def chat_stream(
    body: StreamRequest, request: Request, client: UserClientDep, user: CurrentUserDep
) -> StreamingResponse:
    await require_owned_thread(client, body.thread_id)
    structlog.contextvars.bind_contextvars(thread_id=str(body.thread_id))

    user_messages = [m for m in body.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="messages must contain at least one user message",
        )

    # Demo cost control: block before persisting anything or touching Gemini if the
    # user is out of budget or the month is full. The 429 detail carries a code +
    # message the frontend renders.
    try:
        await enforce_quota(user.id, user.email, client_ip(request))
    except QuotaExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    # Persist the user's question before streaming so a mid-stream client
    # disconnect can't drop it; run_chat_turn persists the assistant reply and
    # its citations at the end of the stream.
    svc = await service_client()
    await thread_db.save_message(svc, body.thread_id, "user", user_messages[-1].content)

    return StreamingResponse(
        run_chat_turn(svc, body.thread_id, user_messages[-1].content, user.id),
        media_type="text/plain; charset=utf-8",
        headers=DATA_STREAM_HEADERS,
    )
