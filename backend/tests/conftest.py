"""Shared test fixtures."""

import uuid
from datetime import date

import pytest

from app.database.models import DocumentChunk, SourceDocument


@pytest.fixture
def make_chunk():
    """Factory for transient DocumentChunk objects with a source document attached.

    Only the fields the agent/grounding/output code reads are populated; the
    instances are never flushed, so the unset NOT NULL columns don't matter.
    """

    def _make(
        *,
        ticker: str = "AAPL",
        fiscal_year: int = 2024,
        content: str = "Revenue rose year over year.",
        section: str | None = "PART II > Item 7. MD&A",
        page: int | None = 34,
        chunk_index: int = 3,
        chunk_id: uuid.UUID | None = None,
    ) -> DocumentChunk:
        document = SourceDocument(
            id=uuid.uuid4(),
            ticker=ticker,
            company=f"{ticker} Inc.",
            cik="0000320193",
            filing_type="10-K",
            filing_date=date(fiscal_year, 11, 1),
            report_date=None,
            fiscal_year=fiscal_year,
            accession_number=f"acc-{uuid.uuid4()}",
            source_url="https://www.sec.gov/example",
            markdown=None,
            word_count=None,
        )
        return DocumentChunk(
            id=chunk_id or uuid.uuid4(),
            document=document,
            document_id=document.id,
            chunk_index=chunk_index,
            content=content,
            token_count=10,
            section=section,
            page=page,
        )

    return _make
