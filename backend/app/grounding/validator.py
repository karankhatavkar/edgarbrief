"""Citation grounding checks — pure, LLM-free, DB-free.

The product contract: an assistant answer either cites retrieved passages or
explicitly refuses for lack of evidence, and it can never cite a chunk that
wasn't retrieved this turn. This module fails closed on either violation.
"""

import uuid
from collections.abc import Mapping

from app.assistant.outputs import AgentReply
from app.database.models import DocumentChunk


class GroundingError(Exception):
    """An answer's citations aren't backed by passages retrieved this turn."""


def validate_grounding(
    reply: AgentReply, retrieved: Mapping[uuid.UUID, DocumentChunk]
) -> None:
    """Raise ``GroundingError`` if ``reply`` violates the grounding contract."""
    if not reply.refused and not reply.citations:
        raise GroundingError(
            "a non-refusal answer must cite at least one retrieved passage"
        )
    ungrounded = [c.chunk_id for c in reply.citations if c.chunk_id not in retrieved]
    if ungrounded:
        raise GroundingError(
            f"citations reference chunks not retrieved this turn: {ungrounded}"
        )
