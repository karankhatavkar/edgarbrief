"""`source_documents` — one SEC filing per row."""

import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import Date, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, TimestampMixin, uuid_pk

if TYPE_CHECKING:
    from app.database.models.document_chunk import DocumentChunk


class SourceDocument(Base, TimestampMixin):
    """A single SEC filing (e.g. one company's 10-K for one fiscal year)."""

    __tablename__ = "source_documents"

    id: Mapped[uuid.UUID] = uuid_pk()
    ticker: Mapped[str] = mapped_column(String, nullable=False)
    company: Mapped[str] = mapped_column(String, nullable=False)
    cik: Mapped[str] = mapped_column(String, nullable=False)
    filing_type: Mapped[str] = mapped_column(String, nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    # SEC accession number — unique, used for idempotent re-ingestion.
    accession_number: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    source_url: Mapped[str] = mapped_column(String, nullable=False)

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
