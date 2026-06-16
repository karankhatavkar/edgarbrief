"""`document_chunks` — retrievable passages with embeddings and FTS vectors."""

import uuid
from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.config import settings
from app.database.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.database.models.source_document import SourceDocument


class DocumentChunk(Base, TimestampMixin):
    """A retrievable passage: its text, its embedding, and an FTS vector."""

    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("source_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Position within the document; used to fetch neighbouring chunks.
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    section: Mapped[str | None] = mapped_column(String)
    page: Mapped[int | None] = mapped_column(Integer)

    embedding: Mapped[list[float]] = mapped_column(
        Vector(settings.gemini_embedding_dimensions), nullable=False
    )
    # Generated column; the GIN index over it is created in the migration.
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
        nullable=False,
    )

    document: Mapped["SourceDocument"] = relationship(back_populates="chunks")
