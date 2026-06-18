"""Chunk loaded source documents, embed the chunks, and write document_chunks.

Run from backend/ (after ingest/load_source_documents.py has populated
source_documents):

    uv run python ingest/chunk_documents.py

Idempotent: a document that already has chunks is skipped, so re-running after
adding new filings is safe. The chunking strategy lives in ingest/chunk.py and
docs/architecture.md.
"""

from __future__ import annotations

from google import genai
from google.genai import types
from sqlalchemy import create_engine, exists, select
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models.document_chunk import DocumentChunk
from app.database.models.source_document import SourceDocument
from ingest.chunk import Chunk, chunk_markdown

# gemini-embedding-001 accepts up to 100 instances per request.
EMBED_BATCH = 100


def _db_url() -> str:
    url = str(settings.database_url)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _embed_input(chunk: Chunk) -> str:
    """Text sent to the embedder: the section breadcrumb leads the chunk body.

    The breadcrumb carries section context (e.g. "Item 1A. Risk Factors") that
    10-K Markdown does not mark inline, so the embedding reflects where the
    passage sits even when it comes from the middle of a long section.
    """
    return f"{chunk.section}\n\n{chunk.content}" if chunk.section else chunk.content


def _embed_all(client: genai.Client, chunks: list[Chunk]) -> list[list[float]]:
    config = types.EmbedContentConfig(
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=settings.gemini_embedding_dimensions,
    )
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), EMBED_BATCH):
        batch = chunks[start : start + EMBED_BATCH]
        response = client.models.embed_content(
            model=settings.gemini_embedding_model,
            contents=[_embed_input(c) for c in batch],
            config=config,
        )
        vectors.extend(e.values for e in response.embeddings)
    return vectors


def main() -> None:
    client = genai.Client(api_key=settings.gemini_api_key)
    engine = create_engine(_db_url())
    chunked = skipped = total_chunks = 0

    with Session(engine) as session:
        documents = session.scalars(
            select(SourceDocument).where(SourceDocument.markdown.is_not(None))
        ).all()

        for doc in documents:
            label = f"{doc.ticker} {doc.fiscal_year}"
            already = session.scalar(
                select(exists().where(DocumentChunk.document_id == doc.id))
            )
            if already:
                print(f"  SKIP  {label}")
                skipped += 1
                continue

            chunks = chunk_markdown(doc.markdown)
            if not chunks:
                print(f"  EMPTY {label}  — no chunks produced")
                continue

            print(f"  EMBED {label}  ({len(chunks)} chunks) ...", end="", flush=True)
            vectors = _embed_all(client, chunks)

            session.add_all(
                DocumentChunk(
                    document_id=doc.id,
                    chunk_index=i,
                    content=chunk.content,
                    token_count=chunk.token_count,
                    section=chunk.section,
                    page=chunk.page,
                    embedding=vector,
                )
                for i, (chunk, vector) in enumerate(zip(chunks, vectors))
            )
            session.commit()

            print(" done")
            chunked += 1
            total_chunks += len(chunks)

    print(
        f"\nDone — {chunked} documents chunked ({total_chunks} chunks), "
        f"{skipped} skipped."
    )


if __name__ == "__main__":
    main()
