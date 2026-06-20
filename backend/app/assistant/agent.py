"""The grounded-answer agent.

A PydanticAI agent that retrieves filing passages through bounded tools, answers
only from what it retrieved, and has its citations enforced against that set by
an output validator. Retrieval and grounding stay in their own modules so they
remain testable without invoking the LLM.
"""

import uuid
from pathlib import Path

from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.google import GoogleModel, GoogleModelSettings
from pydantic_ai.providers.google import GoogleProvider

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import AgentReply, PassageView, chunk_view
from app.config import settings
from app.database.models import DocumentChunk
from app.grounding.validator import GroundingError, validate_grounding
from app.retrieval import retrieve
from app.retrieval.queries import fetch_neighbors, get_chunk_by_id

_INSTRUCTIONS = (Path(__file__).parent / "instructions.md").read_text(encoding="utf-8")

_model = GoogleModel(
    settings.gemini_chat_model,
    provider=GoogleProvider(api_key=settings.gemini_api_key),
    # Cap a single answer's output to bound per-turn Gemini cost on the demo.
    settings=GoogleModelSettings(max_tokens=settings.max_output_tokens),
)

agent = Agent(
    _model,
    output_type=AgentReply,
    deps_type=DocumentAgentDeps,
    instructions=_INSTRUCTIONS,
    retries=2,
)


def _show(deps: DocumentAgentDeps, chunk: DocumentChunk) -> PassageView:
    """Register a chunk as shown to the model and return its view."""
    deps.retrieved[chunk.id] = chunk
    return chunk_view(chunk)


def _parse_chunk_id(chunk_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(chunk_id)
    except ValueError:
        raise ModelRetry(f"'{chunk_id}' is not a valid chunk_id.") from None


@agent.tool
async def search_filings(
    ctx: RunContext[DocumentAgentDeps], query: str
) -> list[PassageView]:
    """Search the SEC 10-K corpus for passages relevant to `query`.

    Returns ranked passages, best first. Cite results by their `chunk_id`.
    """
    async with ctx.deps.session_factory() as session:
        passages = await retrieve(session, query)
    return [_show(ctx.deps, p.chunk) for p in passages]


@agent.tool
async def read_chunk(
    ctx: RunContext[DocumentAgentDeps], chunk_id: str
) -> PassageView | str:
    """Re-read a single passage by its `chunk_id`."""
    async with ctx.deps.session_factory() as session:
        chunk = await get_chunk_by_id(session, _parse_chunk_id(chunk_id))
    if chunk is None:
        return f"No passage found with chunk_id {chunk_id}."
    return _show(ctx.deps, chunk)


@agent.tool
async def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps], chunk_id: str
) -> list[PassageView]:
    """Read the passages immediately before and after `chunk_id` for context."""
    async with ctx.deps.session_factory() as session:
        chunk = await get_chunk_by_id(session, _parse_chunk_id(chunk_id))
        if chunk is None:
            return []
        neighbors = await fetch_neighbors(session, [chunk], window=1)
    ordered = sorted(neighbors, key=lambda c: c.chunk_index)
    return [_show(ctx.deps, n) for n in ordered]


@agent.output_validator
async def enforce_grounding(
    ctx: RunContext[DocumentAgentDeps], reply: AgentReply
) -> AgentReply:
    """Reject any answer whose citations aren't backed by retrieved passages."""
    try:
        validate_grounding(reply, ctx.deps.retrieved)
    except GroundingError as error:
        raise ModelRetry(str(error)) from error
    return reply
