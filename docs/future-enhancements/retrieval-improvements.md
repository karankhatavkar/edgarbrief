# Retrieval Improvements

The baseline hybrid search (pgvector + FTS + RRF) works well for simple single-company, single-year lookups. These four additions close the gaps for the core analyst workflow: cross-company comparisons, multi-year trend questions, and financial table retrieval.

They are listed in priority order — implement them in this sequence.

---

## 1. Metadata Pre-filtering

**What it solves:** Without this, a query like *"Apple's revenue in 2024"* searches all chunks across all filings. Chunks from Apple 2021–2023 compete against 2024 chunks, and the top-K may return the wrong year. The `ticker`, `fiscal_year`, and `filing_type` columns on `source_documents` are wasted if retrieval ignores them.

**How it works:**

Before running any vector or FTS search, make one small structured LLM call to extract filing metadata from the user's query:

```python
# Input query: "Apple's revenue in 2024"
# Extraction output:
{
    "ticker": "AAPL",
    "fiscal_year": 2024,
    "filing_type": "10-K"   # optional — default to 10-K if not specified
}
```

Use that output to pre-select matching `document_id`s from `source_documents`, then pass them as an `IN (...)` filter to both the vector and FTS queries:

```sql
-- Step 1: resolve document IDs from metadata
SELECT id FROM source_documents
WHERE ticker = 'AAPL' AND fiscal_year = 2024;

-- Step 2: vector search, scoped to those documents only
SELECT dc.id, 1 - (dc.embedding <=> $query_vec) AS score
FROM document_chunks dc
WHERE dc.document_id = ANY($filtered_doc_ids)
ORDER BY score DESC
LIMIT 20;

-- Step 3: FTS search, same scope
SELECT dc.id, ts_rank(dc.search_vector, plainto_tsquery('english', $query)) AS score
FROM document_chunks dc
WHERE dc.document_id = ANY($filtered_doc_ids)
  AND dc.search_vector @@ plainto_tsquery('english', $query)
ORDER BY score DESC
LIMIT 20;
```

If extraction fails or the query is ambiguous (no company or year mentioned), fall back to searching all documents — so this degrades gracefully.

**Implementation complexity:** ~50 lines. One small Gemini structured-output call plus an extra `WHERE` clause on both queries.

**Priority:** Highest. This is the single biggest correctness improvement and the cheapest to build.

---

## 2. Adaptive Neighbor Window

**What it solves:** After RRF picks the top chunks, the retriever fetches neighboring chunks (N-1, N, N+1) to handle context that bleeds across chunk boundaries. A fixed ±1 window works for prose but breaks for financial tables, which can span 5–10 chunks. Fetching only ±1 around a financial statement table cuts the income statement in half.

**Current state:** The architecture specifies a default window of ±1. It is not yet adaptive.

**How it works:**

Add an `is_table` boolean column to `document_chunks` during ingestion. The chunker already knows which blocks are tables (they are the atomic table blocks from the chunking algorithm) — set this flag at write time.

```python
# In ingest/chunk.py, when emitting a chunk
chunk = {
    ...
    "is_table": block_type == "table",
}
```

Migration: one nullable boolean column, backfilled to `False` for existing prose chunks.

At query time, use the flag to decide the window size per chunk:

```python
def neighbor_window(chunk: DocumentChunk) -> int:
    if chunk.is_table:
        return 3   # financial tables can be wide
    return 1       # prose default
```

**Example:**

| Section | Chunk content | `is_table` | Window used |
|---|---|---|---|
| Item 1A Risk Factors | "Macroeconomic conditions may adversely affect..." | False | ±1 |
| Item 8 Financial Statements | `\| Revenue \| $394.3B \|...` | True | ±3 |

A query like *"What was total net sales in 2024?"* hits a table chunk. With ±1 the retrieved context contains only 3 chunks of the table. With ±3 it contains 7 chunks — enough to hold the entire income statement.

**Alternative (no schema change):** Inspect `chunk.section` — if it contains `"Item 8"` use a wider window. Less precise but avoids the migration.

**Implementation complexity:** One migration + 5 lines in the retriever.

---

## 3. Per-Year Slot Filling

**What it solves:** For time-range queries like *"how did iPhone revenue shift from 2021–2025?"*, a single RRF pass returns the 10 globally most-similar chunks — which may all be from 2024. You need **guaranteed representation from each year** in the result set, not just the highest-scoring chunks globally.

**How it works:**

1. Metadata extraction (from improvement #1) identifies a year range: `ticker=AAPL, years=[2021, 2022, 2023, 2024, 2025]`.
2. Instead of one retrieval pass, run one hybrid search **per year** in parallel, each returning top-3 chunks.
3. Merge the per-year results into one context.
4. Optionally re-rank the merged set with a second RRF pass if you need to trim to a total budget (e.g. max 15 chunks).

```python
async def retrieve_with_slot_filling(
    query: str,
    query_embedding: list[float],
    ticker: str,
    years: list[int],
    per_year_k: int = 3,
) -> list[DocumentChunk]:
    tasks = [
        hybrid_search(query, query_embedding, ticker=ticker, year=year, k=per_year_k)
        for year in years
    ]
    per_year_results = await asyncio.gather(*tasks)
    # Flatten — each year is guaranteed at least per_year_k chunks
    all_chunks = [chunk for year_chunks in per_year_results for chunk in year_chunks]
    return rrf_fuse(all_chunks)  # optional re-rank to budget
```

**Example:**

Query: *"Compare Apple's gross margin from 2021 to 2024"*

| Without slot filling | With slot filling |
|---|---|
| 8 chunks from 2024, 2 from 2023 | 3 chunks each from 2021, 2022, 2023, 2024 |
| LLM cannot answer 2021–2022 | LLM answers all four years with citations |

**When to trigger it:** Only when metadata extraction returns more than one year (a range or list). Single-year queries go through the normal single-pass retrieval.

**Implementation complexity:** Medium. Requires metadata extraction (#1) to work first. The slot-filling loop itself is ~20 lines.

---

## 4. Query Decomposition

**What it solves:** A question like *"Compare gross margin across Apple, Google, and Microsoft in FY2024"* is three sub-queries in one. A single retrieval pass returns a mixed bag of chunks from all three companies; the LLM then has to synthesize from potentially incomplete per-company context. Decomposing the question into sub-queries and retrieving for each one guarantees complete context per company before generation.

**How it works — two options:**

### Option A: Pre-decompose at the FastAPI layer (simpler, recommended first)

Before invoking the PydanticAI agent, detect multi-part questions at the FastAPI handler and split them:

```python
# Input: "Compare gross margin across Apple, Google, and Microsoft in FY2024"
# Sub-queries after decomposition:
[
    "Apple gross margin FY2024",
    "Google gross margin FY2024",
    "Microsoft gross margin FY2024",
]
```

Run retrieval for each sub-query in parallel (each with its own metadata extraction → hybrid search → RRF → neighbor expansion). Merge all retrieved chunks into one context, then invoke the agent once with the merged context.

**No added LLM round-trip from the agent loop.** The decomposition LLM call is small and structured.

```python
sub_queries = await decompose_query(original_query)   # small LLM call
contexts = await asyncio.gather(*[retrieve(q) for q in sub_queries])
merged_context = deduplicate_chunks(flatten(contexts))
answer = await agent.run(original_query, context=merged_context)
```

### Option B: Agent-driven via a tool (more flexible)

Give the PydanticAI agent a `decompose_query` tool. The agent decides when to call it — no pre-classification needed. The system prompt tells the agent:

> If the question asks about multiple companies or multiple time periods, call `decompose_query` to split it into sub-questions before calling `search_filings`.

The agent calls `decompose_query`, gets back a list of sub-queries, calls `search_filings` for each, then synthesizes one answer.

**Trade-off:** More flexible (the agent decides), but adds at least one extra LLM round-trip per decomposed query, which adds latency.

**When to decompose:**

| Signal | Decompose? |
|---|---|
| Multiple company names ("Apple, Google, Microsoft") | Yes |
| Year range or multiple years ("2021 to 2025") | Use slot filling (#3) instead |
| Single company, single year, single question | No |
| "Compare X and Y" | Yes |

**Implementation complexity:** Medium-high. Requires metadata extraction (#1). Option A is ~30 lines and no agent loop changes. Option B requires a new PydanticAI tool and prompt update.

---

## Summary

| # | Improvement | Complexity | Impact | Depends on |
|---|---|---|---|---|
| 1 | Metadata pre-filtering | Low | High — wrong-year results eliminated | Nothing |
| 2 | Adaptive neighbor window | Low | Medium — financial table retrieval fixed | Nothing (or #1 for `is_table` flag) |
| 3 | Per-year slot filling | Medium | High — multi-year queries answered fully | #1 (year extraction) |
| 4 | Query decomposition | Medium | High — multi-company questions answered fully | #1 (ticker extraction) |

Implement in order. #1 and #2 are independent and can be done in the same PR. #3 and #4 both depend on #1 being in place.
