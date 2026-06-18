"""Chat streaming route.

POST /chat/stream — AI SDK data-stream of one assistant turn (stub in Phase 3).
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.deps import UserClientDep, require_owned_thread
from app.chat.orchestrator import run_chat_turn
from app.chat.streaming import DATA_STREAM_HEADERS
from app.database import threads as thread_db
from app.database.supabase import service_client

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageIn(BaseModel):
    role: str
    content: str


class StreamRequest(BaseModel):
    thread_id: uuid.UUID
    messages: list[ChatMessageIn]


@router.post("/stream")
async def chat_stream(body: StreamRequest, client: UserClientDep) -> StreamingResponse:
    await require_owned_thread(client, body.thread_id)

    user_messages = [m for m in body.messages if m.role == "user"]
    if not user_messages:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="messages must contain at least one user message",
        )

    # Persist the user's question before streaming so a mid-stream client
    # disconnect can't drop it; run_chat_turn persists the assistant reply and
    # its citations at the end of the stream.
    svc = await service_client()
    await thread_db.save_message(svc, body.thread_id, "user", user_messages[-1].content)

    return StreamingResponse(
        run_chat_turn(svc, body.thread_id, user_messages[-1].content),
        media_type="text/plain; charset=utf-8",
        headers=DATA_STREAM_HEADERS,
    )
