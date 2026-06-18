"""Typed agent output and the grounded answer the rest of the system consumes.

The agent emits an ``AgentReply`` (answer + refusal flag + citations). The
authoritative ``cited_passages`` are assembled server-side from the passages the
agent actually retrieved — the model never reproduces passage text, which keeps
a fabricated quote from ever reaching the client.
"""

import uuid
from collections.abc import Mapping
from datetime import date

from pydantic import BaseModel

from app.database.models import DocumentChunk


class PassageView(BaseModel):
    """A compact passage as shown to the model by the retrieval tools."""

    chunk_id: str
    ticker: str
    company: str
    fiscal_year: int
    filing_type: str
    section: str | None
    page: int | None
    content: str


class Citation(BaseModel):
    """A factual claim tied to the chunk that supports it (emitted by the agent)."""

    chunk_id: uuid.UUID
    claim_text: str


class SourcePassage(BaseModel):
    """A cited passage with the metadata the UI needs to show and verify it."""

    passage_index: int
    chunk_id: uuid.UUID
    ticker: str
    company: str
    fiscal_year: int
    filing_type: str
    filing_date: date | None
    section: str | None
    page: int | None
    source_url: str
    excerpt: str


class AgentReply(BaseModel):
    """The agent's raw, validated output. ``cited_passages`` are added later."""

    answer: str
    refused: bool = False
    citations: list[Citation] = []


class GroundedAnswer(BaseModel):
    """The citation-backed answer the orchestrator streams and persists."""

    answer: str
    refused: bool
    citations: list[Citation]
    cited_passages: list[SourcePassage]


def chunk_view(chunk: DocumentChunk) -> PassageView:
    """Map a chunk (with its source document) to the view tools hand the model."""
    document = chunk.document
    return PassageView(
        chunk_id=str(chunk.id),
        ticker=document.ticker,
        company=document.company,
        fiscal_year=document.fiscal_year,
        filing_type=document.filing_type,
        section=chunk.section,
        page=chunk.page,
        content=chunk.content,
    )


def build_grounded_answer(
    reply: AgentReply, retrieved: Mapping[uuid.UUID, DocumentChunk]
) -> GroundedAnswer:
    """Attach authoritative source passages to a (already grounded) reply.

    ``passage_index`` is the chunk's position in the turn's retrieved set
    (insertion order), matching ``message_citations.passage_index``. Assumes
    every citation's chunk is present in ``retrieved`` — the grounding validator
    guarantees this before this runs.
    """
    index_of = {chunk_id: i for i, chunk_id in enumerate(retrieved)}
    seen: set[uuid.UUID] = set()
    cited_passages: list[SourcePassage] = []
    for citation in reply.citations:
        if citation.chunk_id in seen:
            continue
        seen.add(citation.chunk_id)
        chunk = retrieved[citation.chunk_id]
        document = chunk.document
        cited_passages.append(
            SourcePassage(
                passage_index=index_of[citation.chunk_id],
                chunk_id=chunk.id,
                ticker=document.ticker,
                company=document.company,
                fiscal_year=document.fiscal_year,
                filing_type=document.filing_type,
                filing_date=document.filing_date,
                section=chunk.section,
                page=chunk.page,
                source_url=document.source_url,
                excerpt=chunk.content,
            )
        )
    return GroundedAnswer(
        answer=reply.answer,
        refused=reply.refused,
        citations=reply.citations,
        cited_passages=cited_passages,
    )
