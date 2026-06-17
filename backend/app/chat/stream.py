"""Turn orchestration and AI SDK data-stream formatting.

Emits the Vercel AI SDK data-stream protocol so `useChat` works with no
frontend configuration:

  0:"token"\n   — text chunk (JSON-encoded string)
  d:{...}\n     — finish metadata

The frame builders are isolated and unit-tested because this is the wire
contract with the frontend: a typo here silently breaks chat. The user message
is persisted by the route *before* streaming starts (so a mid-stream client
disconnect can't lose the question); this module persists only the assistant
reply, after the last token is yielded.
"""

import json
import uuid
from collections.abc import AsyncGenerator

from supabase import AsyncClient

from app.database import threads as thread_db

# Header that tells the AI SDK client to parse the data-stream protocol below.
DATA_STREAM_HEADERS = {"x-vercel-ai-data-stream": "v1"}

_STUB_TOKENS = (
    "This ",
    "is ",
    "a ",
    "stubbed ",
    "response ",
    "from ",
    "EdgarBrief. ",
    "Real ",
    "retrieval-augmented ",
    "answers ",
    "will ",
    "replace ",
    "this ",
    "in ",
    "Phase ",
    "4.",
)


def text_chunk(text: str) -> str:
    """Format one text token as an AI SDK data-stream line."""
    return f"0:{json.dumps(text)}\n"


def finish_frame(prompt_tokens: int = 0, completion_tokens: int = 0) -> str:
    """Format the terminating finish line of an AI SDK data-stream."""
    payload = {
        "finishReason": "stop",
        "usage": {
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
        },
    }
    return f"d:{json.dumps(payload)}\n"


async def stub_turn(
    thread_id: uuid.UUID,
    svc: AsyncClient,
) -> AsyncGenerator[str, None]:
    """Stream a stub reply, then persist the assistant message.

    Yields AI SDK data-stream lines. The DB write happens after the last yield
    so the client receives the full stream before any blocking I/O.
    """
    full_reply: list[str] = []

    for token in _STUB_TOKENS:
        full_reply.append(token)
        yield text_chunk(token)

    yield finish_frame()

    await thread_db.save_message(svc, thread_id, "assistant", "".join(full_reply))
