"""Runtime dependencies the agent's tools receive via ``RunContext``."""

import uuid
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import DocumentChunk


@dataclass
class DocumentAgentDeps:
    """Per-turn agent state.

    ``retrieved`` accumulates every chunk the tools have shown the model this
    turn, keyed by id in first-seen order. Grounding validates citations against
    it, and citations are assembled from it.
    """

    session: AsyncSession
    retrieved: dict[uuid.UUID, DocumentChunk] = field(default_factory=dict)
