"""Run one grounded chat turn end-to-end and frame it as an AI SDK data-stream.

The agent runs to completion first: grounding is enforced *inside* the run (an
output validator), so by the time we stream a single token the answer's
citations are already verified. A grounding or model failure therefore yields a
controlled error part instead of a polished-but-unsupported answer.
"""

import time
import uuid
from collections.abc import AsyncGenerator

import structlog
from pydantic_ai import UnexpectedModelBehavior
from supabase import AsyncClient

from app.assistant.agent import agent
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import build_grounded_answer
from app.chat.streaming import (
    answer_deltas,
    citations_part,
    error_part,
    finish_frame,
    text_chunk,
)
from app.chat.titling import generate_thread_title
from app.database import threads as thread_db
from app.database.session import async_session
from app.quota import record_usage

log = structlog.get_logger(__name__)


async def _title_first_turn(
    svc: AsyncClient,
    thread_id: uuid.UUID,
    question: str,
    answer: str,
    turn_log: structlog.BoundLogger,
) -> None:
    """Name the thread from its opening exchange, once, best-effort.

    Runs after persistence and after the stream has finished, so a failure here
    can't affect the answer the user already received — we just keep the
    provisional title the thread was created with.
    """
    try:
        # One user + one assistant message means this was the first turn.
        if await thread_db.count_messages(svc, thread_id) != 2:
            return
        title = await generate_thread_title(question, answer)
        if title:
            await thread_db.update_thread_title(svc, thread_id, title)
            turn_log.info("turn.titled", title=title)
    except Exception:
        turn_log.exception("turn.title_failed")


async def run_chat_turn(
    svc: AsyncClient, thread_id: uuid.UUID, question: str, user_id: uuid.UUID
) -> AsyncGenerator[str, None]:
    """Yield AI SDK data-stream lines for one assistant turn, then persist it.

    The user message is persisted by the route before this runs; this persists
    the assistant message and its citations after the stream completes, and
    records the turn's token usage against the caller's demo budget.
    """
    turn_log = log.bind(thread_id=str(thread_id))
    turn_log.info("turn.started")
    start = time.perf_counter()

    deps = DocumentAgentDeps(session_factory=async_session)
    try:
        result = await agent.run(question, deps=deps)
    except UnexpectedModelBehavior:
        # Retries exhausted (grounding couldn't be satisfied) — fail closed.
        turn_log.warning("turn.grounding_failed", retrieved=len(deps.retrieved))
        yield error_part("Could not produce a grounded answer for this question.")
        yield finish_frame()
        return
    except Exception:
        # Retrieval/LLM/DB failure inside the run. We've already sent stream
        # headers, so a raised exception would corrupt the AI-SDK wire protocol:
        # degrade to a controlled error part instead of leaking a 500 mid-stream.
        turn_log.exception("turn.failed", retrieved=len(deps.retrieved))
        yield error_part("Something went wrong while answering. Please try again.")
        yield finish_frame()
        return

    # Bill the whole turn once — `result.usage` already sums every internal step
    # (retries + tool calls). Done before streaming so a client disconnect can't
    # drop the charge.
    usage = result.usage
    await record_usage(user_id, usage.total_tokens, usage.requests)

    grounded = build_grounded_answer(result.output, deps.retrieved)

    for token in answer_deltas(grounded.answer):
        yield text_chunk(token)
    if grounded.cited_passages:
        yield citations_part(
            [passage.model_dump(mode="json") for passage in grounded.cited_passages]
        )
    yield finish_frame(usage.input_tokens, usage.output_tokens)

    passage_index = {p.chunk_id: p.passage_index for p in grounded.cited_passages}
    citation_rows = [
        {
            "chunk_id": str(citation.chunk_id),
            "claim_text": citation.claim_text,
            "passage_index": passage_index[citation.chunk_id],
        }
        for citation in grounded.citations
    ]
    try:
        await thread_db.save_assistant_message(
            svc, thread_id, grounded.answer, citation_rows
        )
    except Exception:
        # The stream already finished, so we can't surface this to the client —
        # log it so a dropped assistant message is debuggable, not silent.
        turn_log.exception("turn.persist_failed")
        return

    await _title_first_turn(svc, thread_id, question, grounded.answer, turn_log)

    turn_log.info(
        "turn.completed",
        citations=len(grounded.citations),
        duration_ms=round((time.perf_counter() - start) * 1000, 1),
    )
