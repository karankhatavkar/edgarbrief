"""Low-level retrieval queries over ``document_chunks``.

Two search arms (semantic via pgvector, lexical via Postgres full-text) plus the
helpers that turn fused ids back into passages: load the winners with their
source document, and pull neighbouring chunks for context. The ``.where``-style
construction here is what later makes a metadata pre-filter a one-line addition.
"""

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database.models import DocumentChunk


async def vector_search(
    session: AsyncSession, query_embedding: Sequence[float], limit: int
) -> list[DocumentChunk]:
    """Top chunks by cosine similarity to the query (uses the HNSW index)."""
    stmt = (
        select(DocumentChunk)
        .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def fulltext_search(
    session: AsyncSession, query_text: str, limit: int
) -> list[DocumentChunk]:
    """Top chunks by lexical match (uses the GIN index on ``search_vector``)."""
    # websearch_to_tsquery tolerates raw user input: quotes, AND/OR, '-' negation.
    tsquery = func.websearch_to_tsquery("english", query_text)
    stmt = (
        select(DocumentChunk)
        .where(DocumentChunk.search_vector.op("@@")(tsquery))
        .order_by(func.ts_rank(DocumentChunk.search_vector, tsquery).desc())
        .limit(limit)
    )
    return list((await session.scalars(stmt)).all())


async def load_anchors(
    session: AsyncSession, ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, DocumentChunk]:
    """Fetch chunks by id with their source document eager-loaded.

    The source document carries the metadata citations need (ticker, fiscal year,
    page, url); async sessions can't lazy-load it later, hence ``selectinload``.
    """
    stmt = (
        select(DocumentChunk)
        .options(selectinload(DocumentChunk.document))
        .where(DocumentChunk.id.in_(ids))
    )
    return {chunk.id: chunk for chunk in (await session.scalars(stmt)).all()}


async def fetch_neighbors(
    session: AsyncSession, anchors: Iterable[DocumentChunk], window: int
) -> list[DocumentChunk]:
    """Chunks within ``±window`` index positions of the anchors, in one round-trip.

    Out-of-range indices (before the first / after the last chunk) simply don't
    match. Returns the anchors' own positions excluded — callers attach by index.
    """
    pairs = {
        (anchor.document_id, anchor.chunk_index + offset)
        for anchor in anchors
        for offset in range(-window, window + 1)
        if offset != 0
    }
    if not pairs:
        return []
    stmt = select(DocumentChunk).where(
        tuple_(DocumentChunk.document_id, DocumentChunk.chunk_index).in_(list(pairs))
    )
    return list((await session.scalars(stmt)).all())
