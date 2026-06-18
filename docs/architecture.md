# EdgarBrief Architecture

## Purpose

EdgarBrief is an internal research assistant for analysts who need grounded answers from a curated SEC filing corpus. The architecture must optimize for trust: every answer is generated from retrieved source passages, every factual claim is citable, and the system fails clearly when the corpus does not support an answer.

This document describes the target architecture for the chat experience, LLM orchestration, and the communication layer between the React SPA, Supabase, and FastAPI backend.

## High-Level Architecture

The best opening diagram is a service-level view that shows the two core paths: the live chat path that serves users, and the ingestion path that prepares SEC filings for retrieval.

```mermaid
flowchart LR
    user[Analyst] --> browser[Browser<br/>React chat app]

    subgraph railway[Railway]
        frontend[Frontend service<br/>Vite build]
        backend[Backend service<br/>FastAPI + PydanticAI]
    end

    subgraph supabase[Supabase]
        auth[Auth<br/>email session]
        db[(Postgres<br/>chats, documents, chunks<br/>pgvector + full-text)]
    end

    gemini[Google Gemini<br/>LLM + embeddings]
    corpus[SEC filing corpus]
    ingestion[Ingestion pipeline<br/>download, parse, chunk, embed]

    frontend -->|serves app| browser
    browser -->|sign in| auth
    auth -->|JWT session| browser
    browser -->|chat request + JWT| backend
    backend -->|verify user| auth
    backend -->|retrieve passages<br/>persist chats + citations| db
    backend -->|generate grounded answer| gemini
    backend -->|stream answer + citations| browser

    corpus --> ingestion
    ingestion -->|create embeddings| gemini
    ingestion -->|store documents + chunks| db
```

## Architectural Goals

- Keep the browser thin: it renders chat state, manages the user's Supabase session, and streams assistant responses.
- Keep the backend authoritative: retrieval, grounding, citation checks, tool execution, and database writes happen in FastAPI.
- Use Supabase for identity and durable product state: users, chat threads, source documents, chunks, embeddings, and citation metadata.
- Use Supabase `pgvector` for semantic retrieval and Postgres full-text search for keyword retrieval.
- Make the LLM path typed and testable by using PydanticAI agents with explicit dependencies, outputs, and tool boundaries.
- Preserve a simple deployment model on Railway: one frontend service, one stateless backend service, and hosted Supabase.

## Stack

Frontend:

- Vite + React SPA + TypeScript
- React Router for routing
- Tailwind CSS and shadcn/ui for UI
- `@supabase/supabase-js` for browser auth
- Vercel AI SDK UI packages for chat state and streaming client behavior

Backend:

- Python 3.12+
- FastAPI + Uvicorn
- Pydantic v2 + pydantic-settings
- PydanticAI for typed LLM orchestration
- Google Gemini SDK (`google-genai`) for generation and embeddings
- Supabase Python client for server-side database access
- SQLAlchemy models + Alembic migrations for schema management
- Supabase `pgvector` for semantic search
- Postgres full-text search for lexical retrieval
- `httpx` for outbound HTTP
- `structlog` for structured logs

Persistence:

- Supabase Auth for email login
- Supabase Postgres for user records, chat threads, chat messages, source documents, chunks, embeddings, full-text search vectors, and citation metadata

## System Boundaries

The frontend is responsible for user interaction, local UI state, and sending the authenticated user's request to the backend. It should never hold service-role credentials, run retrieval logic, call Gemini directly, or write privileged records to Supabase.

The backend is responsible for request authorization, retrieval, prompt construction, LLM execution, citation validation, streaming responses, and durable persistence. It owns all privileged credentials and is the only service allowed to use the Supabase service-role key.

Supabase is responsible for authentication and durable product state. Browser access uses the anon key and user JWT. Server access uses either the user's bearer token for user-scoped operations or the service-role key for privileged writes that must still be explicitly tied to the authenticated user.

## Request Flow

1. The user signs in with Supabase email auth in the React SPA.
2. The frontend stores the Supabase session through `@supabase/supabase-js`.
3. When the user opens a chat, the frontend loads the thread and prior messages through FastAPI, which reads user-scoped records from Supabase.
4. The chat UI uses the Vercel AI SDK React primitives to manage message state and submit new user messages to the FastAPI chat endpoint.
5. The frontend sends the Supabase access token as `Authorization: Bearer <token>`.
6. FastAPI verifies the token with Supabase Auth before doing any retrieval or LLM work.
7. FastAPI creates a request-scoped context containing the authenticated user, chat thread, Supabase client, retrieval service, citation policy, and LLM settings.
8. A PydanticAI agent retrieves relevant document chunks, generates a grounded answer, and returns typed output containing answer text and citations.
9. FastAPI streams assistant message parts back to the browser in the format expected by the AI SDK client.
10. FastAPI persists the final user message, assistant message, cited chunks, and usage metadata to Supabase.

## Frontend Chat Layer

The frontend remains a plain Vite SPA. It should not adopt Next.js route handlers or server components. The AI SDK is used only for its React chat primitives and streaming client behavior.

The chat module should be organized around these responsibilities:

- `src/lib/env.ts` validates `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY`.
- `src/lib/supabase.ts` creates the browser Supabase client.
- `src/lib/http.ts` wraps `fetch`, applies the backend base URL, injects the Supabase bearer token, handles timeouts, and converts failures into typed API errors.
- `src/lib/api.ts` exposes product-level calls such as loading threads, creating threads, and fetching message history.
- `src/pages/chat/*` renders chat routes and delegates chat streaming to a focused chat component.
- `src/components/chat/*` renders messages, citations, source passages, empty states, and streaming status.

The chat component should initialize with stored messages and then let the AI SDK manage in-flight UI state. The transport points to FastAPI, not to a frontend server route.

Conceptual shape:

```ts
const { messages, sendMessage, status, error } = useChat({
  id: threadId,
  messages: initialMessages,
  transport: new DefaultChatTransport({
    api: `${apiBaseUrl}/chat/stream`,
    headers: async () => ({
      Authorization: `Bearer ${await getAccessToken()}`,
    }),
  }),
});
```

The exact API surface should be verified during implementation against the installed AI SDK version. The architectural rule is stable: the browser streams to FastAPI with the user's Supabase token, and FastAPI owns the assistant run.

## Backend LLM Layer

PydanticAI should be introduced as the backend's orchestration layer for answer generation. It replaces ad hoc prompt calls with a typed agent boundary.

Recommended backend modules:

```text
backend/app/
├── api/
│   └── chat.py                 # FastAPI routes for chat threads and streaming
├── auth/
│   └── dependencies.py         # Supabase JWT verification and current user dependency
├── chat/
│   ├── orchestrator.py         # Coordinates one chat turn end-to-end
│   ├── messages.py             # Converts AI SDK messages to and from internal message types
│   └── streaming.py            # Emits AI SDK-compatible streaming events
├── assistant/
│   ├── agent.py                # PydanticAI agent definition
│   ├── deps.py                 # Runtime dependency dataclass for the agent
│   ├── outputs.py              # GroundedAnswer, Citation, and SourcePassage
│   └── instructions.md         # System instructions and product contract
├── retrieval/
│   ├── queries.py              # pgvector and full-text SQL queries
│   ├── fusion.py               # Reciprocal Rank Fusion for hybrid search
│   └── retriever.py            # Query-to-source-passage retrieval logic
├── grounding/
│   └── validator.py            # Ensures citations map to retrieved passages
└── database/
    ├── supabase.py             # Supabase client construction
    ├── models.py               # SQLAlchemy table models used by Alembic autogenerate
    ├── chats.py                # Chat, thread, message, and citation persistence
    └── documents.py            # Source document, chunk, embedding, and search queries
```

These names should follow the product workflow rather than a generic service layer. `chat/orchestrator.py` owns the full turn lifecycle, `assistant/agent.py` owns the LLM boundary, `retrieval/` owns hybrid source-passage search, and `grounding/` owns the trust contract that answers must cite retrieved evidence.

The agent should receive explicit dependencies rather than reaching into globals:

```python
@dataclass
class DocumentAgentDeps:
    user_id: str
    thread_id: str
    retriever: DocumentRetriever
    grounding_validator: GroundingValidator


class GroundedAnswer(BaseModel):
    answer: str
    citations: list[Citation]
    cited_passages: list[SourcePassage]
```

The agent's instructions should encode the product contract:

- Answer only from retrieved passages.
- Cite every factual claim.
- If the retrieved context is insufficient, say that the corpus does not contain enough evidence.
- Do not provide stock recommendations or investment advice.
- Keep answers concise enough for analyst review, but include enough cited passages to verify the answer.

Retrieval and grounding remain independent from PydanticAI. This keeps ingestion, retrieval tests, and citation validation testable without invoking the LLM.

## Ingestion Pipeline

The ingestion pipeline converts raw SEC filings into retrieval-ready chunks stored in Supabase. It runs offline before any user query is served.

```
SEC EDGAR
    │
    ▼
data/download.py          ← fetches raw .htm filings into data/downloads/<year>/
    │
    ▼
data/convert.py           ← two-stage HTM → Markdown conversion
    │   Stage 1: EDGAR HTML Cleaner (BeautifulSoup)
    │   Stage 2: docling DocumentConverter
    │
    ▼
data/markdown/<year>/*.md ← normalized Markdown, one file per filing
    │
    ▼
backend/ingest/           ← chunk, embed, write to Supabase
    │
    ▼
Supabase Postgres         ← source_documents + document_chunks (text, embedding, tsvector)
```

### HTM → Markdown conversion (`data/convert.py`)

EDGAR 10-K filings are published in Inline XBRL (iXBRL) format. Every financial table cell carries a `colspan` attribute (typically `colspan="3"`) for XBRL data alignment. A vanilla HTML converter expands each spanned cell into N identical copies, making 83–96% of financial table rows triplicate. A custom two-stage pipeline is used instead.

**Stage 1 — EDGAR HTML Cleaner** runs three transforms before docling sees the file:

1. *Strip the hidden XBRL block.* Each filing embeds up to 300 KB of machine-readable `<div style="display:none">` metadata at the top. This is invisible in a browser and is removed before conversion.
2. *Normalize table colspans.* The cleaner strips all `colspan` attributes so every cell occupies exactly one column, then removes columns that are empty in every row. This eliminates the phantom duplicate values that EDGAR's XBRL alignment colspans produce. Empty tables are removed entirely.
3. *Inject semantic headings.* Plain `<div>` and `<p>` tags holding `PART I/II/III/IV` and `Item N[A-C].` text are replaced with `<h2>` / `<h3>` tags so docling emits proper `##` / `###` Markdown headings. This is critical for heading-based chunk splitting downstream.

**Stage 2 — docling** (`DocumentConverter`, `compact_tables=True`) handles all prose: paragraphs, lists, in-document anchor links, and image placeholders. The cleaned HTML is passed as a `DocumentStream`.

Result: duplication drops from 29–44% to 1–5%, phantom tables are eliminated, and all Part/Item labels become navigable Markdown headings. See `data/README.md` for full quality metrics.

### Chunking and embedding (backend/ingest/)

After conversion the ingest scripts:

1. Read normalized Markdown files and the `manifest.json` filing metadata.
2. Split each document into chunks with the heading-anchored, token-bounded strategy described below.
3. Write one `source_documents` row per filing (ticker, filing type, date, accession number, normalized Markdown content).
4. Embed each chunk with Gemini `text-embedding-004` (768 dimensions).
5. Write one `document_chunks` row per chunk (text, embedding vector, generated `tsvector`, metadata JSON).
6. Idempotent: skip documents already present in Supabase.

Chunk metadata JSON includes: `ticker`, `company`, `filing_type`, `filing_date`, `fiscal_year`, `accession_number`, `chunk_index`, `section` (from the nearest `##`/`###` heading), `token_count`, and source byte offsets into the Markdown. The section field is populated from the heading hierarchy that Stage 1 injected — without it, every chunk would have an empty section label.

#### Chunking strategy

The chunker is a small, owned module (no third-party text splitter — see the dependency policy in `CLAUDE.md`). It is **heading-anchored and token-bounded with atomic table handling**, chosen for the specific shape of the corpus rather than a generic default.

**Why this shape.** A 10-K has a strong but shallow structure. After Stage 1 heading injection, every filing carries exactly the same skeleton: four `## PART I–IV` headings and ~22–30 `### Item N` headings, with **no deeper headings** — the sub-sections inside an Item (e.g. individual risk factors, "Macroeconomic and Industry Risks") are plain prose, not marked up. So `### Item` is the deepest reliable structural boundary. Item sizes also span four orders of magnitude in the same document: tiny stubs like *Item 1B. Unresolved Staff Comments* (~1 token) or *Item 4. Mine Safety Disclosures* (~16 tokens) sit beside *Item 1A. Risk Factors* (~12,900 tokens) and *Item 8. Financial Statements* (~19,300 tokens). Item 8 is dominated by large multi-column financial tables. Two naive approaches are therefore ruled out: one-chunk-per-Item is impossible because the largest Items dwarf the embedder's ~2,048-token input cap, and fixed-size windowing ignores the structure entirely — it splits tables mid-row (discarding the whole point of `convert.py`) and produces unusable citations.

**Parameters** (tuned to the `text-embedding-004` input cap and retrieval precision):

- Target ≈ **512 tokens**, hard max ≈ **800**, min ≈ **64** (so tiny Items stay whole rather than merging across boundaries).
- Overlap ≈ one paragraph / ~80 tokens between adjacent prose chunks, so a thought split across a boundary is still retrievable. `read_surrounding_chunks` recovers wider context at query time.

**Algorithm:**

1. **Pre-clean.** Strip the repeating page-footer lines (`… Form 10-K | <page>`) and `#i…` anchor-link artifacts that survive conversion, so they do not pollute chunk text or embeddings.
2. **Hard-split on headings.** A chunk never crosses a `### Item` (or `## PART`) boundary. The heading breadcrumb (e.g. `PART I > Item 1A. Risk Factors`) is carried down to every chunk in that section.
3. **Pack blocks within a section.** Walk the section's top-level blocks (paragraphs separated by blank lines, and tables):
   - **Prose:** greedily pack whole paragraphs until the next would exceed the max, emit the chunk, then start the next one with the overlap paragraph. If a single paragraph exceeds the max, fall back to sentence splitting.
   - **Tables:** treat each Markdown table plus its caption line (e.g. `CONSOLIDATED STATEMENTS OF OPERATIONS`) as one **atomic block**. If a single table exceeds the max, split it on **row boundaries only**, repeating the header row and caption in each piece. Never split a row.
4. **Prefix the breadcrumb into embedded text.** Each chunk's embedded text begins with its breadcrumb. This injects the section context that docling could not mark inline, so "Risk Factors" / "Item 8" semantics ride along even for a chunk taken from the middle of a long section.
5. **Emit metadata** as listed above, including a stable per-document `chunk_index` so neighbor lookups and citations stay ordered.

**Worked example.** *Item 1A. Risk Factors* (~12,900 tokens) becomes ~25 prose chunks of ~512 tokens, each prefixed `PART I > Item 1A. Risk Factors` and overlapping its predecessor by one paragraph. The *Consolidated Statements of Operations* table inside *Item 8* (~600 tokens) stays as a single intact chunk prefixed `PART II > Item 8. Financial Statements`, so a query like "What was total net sales in 2024?" retrieves the whole table with a clean Item-level citation, and "What macroeconomic risks does the company cite?" retrieves a focused Item 1A chunk.

## Retrieval Strategy

EdgarBrief uses hybrid retrieval:

1. Embed the user's query with the configured Gemini embedding model (`text-embedding-004`, 768 dimensions).
2. Run a semantic search over `document_chunks.embedding` with `pgvector`.
3. Run a lexical search over `document_chunks.search_vector` with Postgres full-text search.
4. Fuse the two ranked lists in Python with Reciprocal Rank Fusion.
5. Fetch the selected chunks, source document metadata, and optional neighboring chunks for grounding.

This keeps the database responsible for efficient ranked retrieval and keeps the application responsible for product-specific ranking policy. The first implementation should avoid agent-generated SQL; the PydanticAI agent receives bounded tools such as `search_filings`, `read_chunk`, and `read_surrounding_chunks`.

## Supabase and FastAPI Communication

Supabase Auth is the identity source. FastAPI must treat the browser's Supabase JWT as the request credential.

Frontend rules:

- Use the anon key only in the browser.
- Read the current session through the shared Supabase client.
- Send the access token to FastAPI through the shared API client.
- Never pass tokens through component props.
- Never expose the service-role key to the frontend.

Backend rules:

- Verify `Authorization: Bearer <token>` at the FastAPI boundary.
- Reject unauthenticated requests before retrieval or LLM work.
- Derive `user_id` and email from the verified Supabase user.
- Use user-scoped database operations wherever possible.
- Use the service-role key only on the backend for privileged writes that cannot be safely performed with the anon key.
- Always attach persisted chat records to the authenticated `user_id`.

The backend can verify the JWT by calling Supabase Auth's user endpoint or by validating the project's JWT signing keys. For the first implementation, calling Supabase Auth is simpler and avoids local JWT validation mistakes. If request volume grows, local JWT verification can be added behind the same `AuthService` interface.

Recommended backend units:

- `app/auth/dependencies.py` validates bearer tokens and exposes `get_current_user`.
- `app/database/supabase.py` creates user-scoped and admin Supabase clients.
- `app/database/chats.py` stores and reads chat threads, messages, and citation records.
- `app/database/documents.py` stores and reads source documents, chunks, embeddings, and full-text search data.

## Streaming Contract

The frontend should receive incremental assistant output, not wait for a full answer. FastAPI should expose a streaming endpoint that emits AI SDK-compatible message parts.

Recommended endpoint:

```text
POST /chat/stream
Authorization: Bearer <supabase_access_token>
Content-Type: application/json
```

Request body:

```json
{
  "threadId": "uuid",
  "messages": []
}
```

The `messages` payload should use the AI SDK UI message format at the frontend boundary. FastAPI can translate that wire format into internal Pydantic models before invoking the agent.

Streaming responsibilities:

- Send text deltas as the answer is generated.
- Send citation/source metadata as structured parts once available.
- Send clear error events for authentication failures, missing threads, retrieval failures, and grounding failures.
- Persist only after the assistant run completes successfully, unless a separate partial-message model is deliberately introduced later.

## Data Model

Supabase tables should be small and product-oriented:

- `users`: one row per authenticated user, keyed by Supabase `auth.users.id`.
- `chat_threads`: thread metadata, owner, title, timestamps.
- `chat_messages`: user and assistant messages in order, with AI SDK-compatible message JSON where useful.
- `message_citations`: normalized citation records linked to assistant messages.
- `source_documents`: original document records with filing metadata, source URL, and normalized Markdown content.
- `document_chunks`: chunk text, chunk metadata, embeddings, and generated full-text search vectors.

`source_documents` stores the normalized Markdown version of each filing so the application can re-chunk, inspect, and cite the original extracted text without reaching back into downloaded HTML files. `document_chunks` stores retrieval-ready passages:

- chunk ID
- document ID
- chunk index
- page or section metadata
- chunk text
- embedding vector
- generated `tsvector` for full-text search
- token count
- metadata JSON for ticker, company, filing type, filing date, year, accession number, page, section, and source offsets

Hybrid retrieval runs two bounded queries against `document_chunks`: a semantic `pgvector` query and a Postgres full-text query. The backend fuses those ranked lists with Reciprocal Rank Fusion, then fetches the selected chunks and neighboring context for grounding.

## Schema Management

Database schema changes are managed from the backend with SQLAlchemy models and Alembic migrations. Supabase is the hosted Postgres database, but the Supabase dashboard is not the source of truth for table definitions.

The workflow is:

1. Update SQLAlchemy models in `app/database/models.py`.
2. Generate a candidate migration with `uv run alembic revision --autogenerate -m "<change>"`.
3. Review the generated migration file in `backend/alembic/versions/`.
4. Add explicit migration operations for Postgres/Supabase features that autogenerate cannot infer reliably.
5. Apply the migration locally or against the linked Supabase database with `uv run alembic upgrade head`.
6. Commit both the model changes and the migration file.

Normal tables and ordinary indexes should be represented in SQLAlchemy models where practical. The following should be written explicitly in migrations with `op.execute()` or carefully reviewed Alembic operations:

- `create extension if not exists vector`
- `vector(768)` embedding columns if the SQLAlchemy type renderer is not sufficient
- generated `tsvector` columns
- HNSW indexes for vector search
- GIN indexes for full-text search and JSON metadata
- RLS enablement and policies
- grants or Supabase role-specific permissions

Alembic must connect with Supabase's direct/session database connection string. Do not run migrations through the transaction pooler URL, because schema migrations, extension setup, and index creation require session-level database behavior.

## Grounding and Citation Policy

Grounding is part of the architecture, not a prompt preference.

The backend should enforce these invariants:

- Every assistant answer has at least one citation unless the answer explicitly says there is not enough evidence.
- Every citation maps to a retrieved source passage.
- Cited passages include enough metadata for the frontend to show company, filing, date, page or section, and excerpt.
- The model cannot cite documents that were not retrieved for the current request.
- If citation validation fails, the backend returns a controlled failure instead of a polished unsupported answer.

This policy should be covered by backend unit tests around retrieval, citation extraction, and grounding enforcement.

## Error Handling

Expected error classes:

- `401 Unauthorized`: missing, expired, or invalid Supabase token.
- `403 Forbidden`: authenticated user tries to access another user's thread.
- `404 Not Found`: thread or source document does not exist.
- `422 Unprocessable Entity`: invalid request payload.
- `502 Bad Gateway`: upstream LLM or Supabase failure.
- `500 Internal Server Error`: unexpected backend failure.

The frontend should render friendly messages while preserving enough technical detail in logs for debugging. Network and CORS failures should be distinguishable from HTTP failures in the shared API client.

## Configuration

Each service must keep one settings module as the source of truth.

Frontend settings:

- `VITE_API_BASE_URL`
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Backend settings:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `DATABASE_URL` for Alembic and direct Postgres access
- `GEMINI_API_KEY`
- `ALLOWED_ORIGINS`
- embedding model name and dimensions

Do not read environment variables directly from components, route handlers, or services. Frontend code should use `src/lib/env.ts`. Backend code should use `app/config.py`.

## Deployment Shape

Railway should run two services:

- Frontend: static Vite build served as a web app.
- Backend: FastAPI service running Uvicorn.

Supabase remains hosted and stores the durable retrieval data. The Railway backend can stay stateless because document chunks, embeddings, full-text search vectors, chats, and citations all live in Supabase Postgres. Raw downloaded filings remain gitignored local ingestion inputs unless a later workflow stores them in object storage.

## Implementation Sequence

1. Scaffold the frontend SPA and backend FastAPI app according to the repo conventions.
2. Add SQLAlchemy models and Alembic migration setup in the backend.
3. Add the initial Alembic migration for `pgvector`, source document, chunk, full-text, chat, and citation tables.
4. Add Supabase Auth in the frontend and token verification in FastAPI.
5. Add the shared frontend API client with automatic bearer-token injection.
6. Add the chat streaming endpoint with a stubbed assistant response.
7. Add AI SDK chat UI on the frontend pointed at FastAPI.
8. Add Markdown ingestion, chunking, embeddings, and Supabase writes.
9. Add semantic search with `pgvector`.
10. Add Postgres full-text search and Python RRF fusion.
11. Add PydanticAI document agent with typed dependencies and typed answer output.
12. Add citation validation and grounding enforcement.
13. Add final UI for citations, source passages, empty states, and errors.

## Non-Goals

- No Next.js, SSR, server components, or frontend route handlers.
- No direct Gemini calls from the browser.
- No separate managed vector database outside Supabase.
- No multi-tenant architecture.
- No external market/news data.
- No trading recommendations or generated stock picks.
