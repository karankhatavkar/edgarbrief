"""Embed a user query for semantic retrieval.

The asymmetric counterpart to ingestion's ``RETRIEVAL_DOCUMENT`` embedding
(``ingest/chunk_documents.py``): queries use ``RETRIEVAL_QUERY`` so they land in
the same space as the stored chunk vectors. No section breadcrumb is prepended —
that context belongs to documents, not questions — and no normalization is
needed because retrieval ranks by cosine distance, which is scale-invariant.
"""

from google import genai
from google.genai import types

from app.config import settings

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


async def embed_query(text: str) -> list[float]:
    config = types.EmbedContentConfig(
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=settings.gemini_embedding_dimensions,
    )
    # .aio keeps the embedding call off the event loop's blocking path.
    response = await _get_client().aio.models.embed_content(
        model=settings.gemini_embedding_model,
        contents=[text],
        config=config,
    )
    return response.embeddings[0].values
