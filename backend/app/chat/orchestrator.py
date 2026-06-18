"""Run one grounded chat turn end-to-end and frame it as an AI SDK data-stream.

The agent runs to completion first: grounding is enforced *inside* the run (an
output validator), so by the time we stream a single token the answer's
citations are already verified. A grounding or model failure therefore yields a
controlled error part instead of a polished-but-unsupported answer.
"""

import uuid
from collections.abc import AsyncGenerator

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
from app.database import threads as thread_db
from app.database.session import async_session


async def run_chat_turn(
    svc: AsyncClient, thread_id: uuid.UUID, question: str
) -> AsyncGenerator[str, None]:
    """Yield AI SDK data-stream lines for one assistant turn, then persist it.

    The user message is persisted by the route before this runs; this persists
    the assistant message and its citations after the stream completes.
    """
    async with async_session() as session:
        deps = DocumentAgentDeps(session=session)
        try:
            result = await agent.run(question, deps=deps)
        except UnexpectedModelBehavior:
            # Retries exhausted (grounding couldn't be satisfied) — fail closed.
            yield error_part(
                "Could not produce a grounded answer for this question."
            )
            yield finish_frame()
            return

        grounded = build_grounded_answer(result.output, deps.retrieved)

    for token in answer_deltas(grounded.answer):
        yield text_chunk(token)
    if grounded.cited_passages:
        yield citations_part(
            [passage.model_dump(mode="json") for passage in grounded.cited_passages]
        )
    yield finish_frame()

    passage_index = {p.chunk_id: p.passage_index for p in grounded.cited_passages}
    citation_rows = [
        {
            "chunk_id": str(citation.chunk_id),
            "claim_text": citation.claim_text,
            "passage_index": passage_index[citation.chunk_id],
        }
        for citation in grounded.citations
    ]
    await thread_db.save_assistant_message(
        svc, thread_id, grounded.answer, citation_rows
    )
