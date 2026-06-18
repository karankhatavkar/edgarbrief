"""Hybrid retrieval: embed → search both arms → fuse → expand with neighbours.

``retrieve`` is the public surface the assistant (Phase 6) calls. It returns
ranked ``RetrievedPassage`` objects, each carrying its source document (for
citations) and the chunks immediately surrounding it (for context).
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DocumentChunk
from app.retrieval.embedding import embed_query
from app.retrieval.fusion import DEFAULT_RRF_K, reciprocal_rank_fusion
from app.retrieval.queries import (
    fetch_neighbors,
    fulltext_search,
    load_anchors,
    vector_search,
)

# Candidates pulled from each arm before fusion; wider than top_k so a chunk the
# two arms rank differently still has a chance to surface.
FANOUT = 20
DEFAULT_TOP_K = 10
NEIGHBOR_WINDOW = 1


@dataclass
class RetrievedPassage:
    """A ranked hit plus the context needed to cite and read it.

    ``chunk.document`` is eager-loaded (ticker, fiscal year, page, url).
    ``neighbors`` are the adjacent chunks within the window, ordered by
    ``chunk_index`` and excluding ``chunk`` itself.
    """

    chunk: DocumentChunk
    neighbors: list[DocumentChunk]
    score: float


async def retrieve(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    fanout: int = FANOUT,
    neighbor_window: int = NEIGHBOR_WINDOW,
) -> list[RetrievedPassage]:
    query_embedding = await embed_query(query)

    vector_hits = await vector_search(session, query_embedding, limit=fanout)
    fulltext_hits = await fulltext_search(session, query, limit=fanout)

    fused = reciprocal_rank_fusion(
        [[c.id for c in vector_hits], [c.id for c in fulltext_hits]],
        k=DEFAULT_RRF_K,
    )[:top_k]

    anchors_by_id = await load_anchors(session, [chunk_id for chunk_id, _ in fused])
    # Fusion can rank an id that a concurrent delete removed; skip the miss.
    ranked = [
        (anchors_by_id[chunk_id], score)
        for chunk_id, score in fused
        if chunk_id in anchors_by_id
    ]

    neighbors = await fetch_neighbors(
        session, (anchor for anchor, _ in ranked), neighbor_window
    )
    neighbors_by_document: dict[uuid.UUID, list[DocumentChunk]] = defaultdict(list)
    for neighbor in neighbors:
        neighbors_by_document[neighbor.document_id].append(neighbor)

    passages = []
    for anchor, score in ranked:
        adjacent = sorted(
            (
                n
                for n in neighbors_by_document[anchor.document_id]
                if abs(n.chunk_index - anchor.chunk_index) <= neighbor_window
                and n.id != anchor.id
            ),
            key=lambda n: n.chunk_index,
        )
        passages.append(RetrievedPassage(chunk=anchor, neighbors=adjacent, score=score))
    return passages
