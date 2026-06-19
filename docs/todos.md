# EdgarBrief — Implementation Checklist

Work top to bottom. Each phase unlocks the next. Check items off as you go.

The critical path is: **data model → ingestion → retrieval → LLM → citations → streaming → frontend**.

---

## Phase 0 — Prerequisites & credentials

- [x] Verify toolchain: Python 3.12+, `uv`, Node 20+, `pnpm`
- [x] Create Supabase project (see `docs/guides/supabase-setup.md`)
- [x] Collect all Supabase credentials: URL, anon key, service_role key, direct DATABASE_URL
- [x] Create Google Gemini API key at [aistudio.google.com](https://aistudio.google.com)
- [x] Copy `backend/.env.example` → `backend/.env` and fill in all values (replace the OpenAI stubs with Gemini ones)
- [x] Copy `frontend/.env.example` → `frontend/.env` and fill in Supabase URL + anon key
- [x] Verify Supabase Auth → email provider is enabled; disable "Confirm email" for local dev

---

## Phase 1 — Backend scaffold & database

**Goal:** a running FastAPI service with a migrated Supabase schema.

- [x] Init backend deps and project layout ([backend-setup](#appendix--quick-reference))
- [x] `app/config.py` — settings module, fail fast on missing env vars
- [x] `app/main.py` — FastAPI app, CORS, health check (`GET /health`)
- [x] SQLAlchemy models in `app/database/models.py`:
  - [x] `users`
  - [x] `source_documents`
  - [x] `document_chunks` (embedding + generated `tsvector`)
  - [x] `chat_threads`
  - [x] `chat_messages`
  - [x] `message_citations`
- [x] Alembic init + first migration:
  - [x] `create extension if not exists vector`
  - [x] `vector(768)` embedding column
  - [x] generated `tsvector` column on chunks
  - [x] HNSW index (vector) + GIN index (full-text)
  - [x] RLS policies (users see only their own chats)
- [x] `uv run alembic upgrade head` against Supabase direct connection
- [x] `app/database/supabase.py` — user-scoped and service-role clients
- [x] Verify: `uv run uvicorn app.main:app --reload` → health check returns 200

---

## Phase 2 — Auth (full stack)

Goal: analysts can sign in with email; backend rejects unauthenticated requests.

**Backend**

- [x] `app/auth/dependencies.py` — verify `Authorization: Bearer <supabase_jwt>`, expose `get_current_user`
- [x] Reject missing/expired tokens with `401` before any chat or retrieval work

**Frontend**

- [x] Scaffold Vite + React + TypeScript + Tailwind + shadcn ([frontend-setup](guides/frontend-setup.md))
- [x] `src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [x] `src/lib/supabase.ts` — browser Supabase client
- [x] `src/lib/http.ts` + `src/lib/api.ts` — fetch wrapper with automatic bearer token
- [x] Sign-in / sign-up pages (email only, no SSO)
- [x] Protected routes — redirect unauthenticated users to login
- [x] Verify: sign up, sign in, token reaches backend on a test authenticated endpoint

---

## Phase 3 — Chat shell (vertical slice, stubbed)

**Goal:** end-to-end chat UI streaming from FastAPI, no real retrieval yet.

**Backend**

- [x] Chat thread CRUD: list threads, create thread, load message history
- [x] `POST /chat/stream` — accepts AI SDK message format, streams a stubbed assistant reply
- [x] Persist user + assistant messages to `chat_messages` after stream completes
- [x] `403` when user accesses another user's thread

**Frontend**

- [x] React Router: login, chat list, chat thread routes
- [x] AI SDK chat primitives pointed at `POST /chat/stream` with Supabase bearer token
- [x] Thread sidebar (past conversations)
- [x] Basic message list + input + streaming indicator
- [x] Verify: create thread, send message, see streamed stub response, reload and see history

---

## Phase 4 — Ingestion pipeline

**Goal:** SEC filings in the corpus are parsed, chunked, embedded, and stored in Supabase.

- [x] `ingest/` scripts (or CLI entrypoint) for one-off corpus loading
- [x] HTML → normalized Markdown extraction (preserve page/section metadata)
- [x] Chunking strategy (size + overlap; store chunk index, page, section, ticker, filing type, year)
- [x] Write `source_documents` rows with filing metadata from `manifest.json`
- [x] Write `document_chunks` rows with text + metadata
- [x] Gemini embedding generation (`gemini-embedding-001`) → store `vector(768)` per chunk
- [x] Generated `tsvector` populated for full-text search
- [x] Idempotent re-run (skip already-ingested documents)
- [x] Unit tests: chunking logic, metadata extraction 
- [x] Run ingestion on full sample corpus (25 filings × 5 companies)
- [x] Verify: chunks exist in Supabase; spot-check a known passage (e.g. Apple revenue mix table)

---

## Phase 5 — Retrieval

Goal: a user question returns ranked, relevant source passages.

- [x] `retrieval/queries.py` — pgvector semantic search over `document_chunks`
- [x] `retrieval/queries.py` — Postgres full-text search over `search_vector`
- [x] `retrieval/fusion.py` — Reciprocal Rank Fusion in Python
- [x] `retrieval/retriever.py` — query → fused ranked passages + neighbor chunks
- [x] Unit tests: fusion ranking, query assembly (mock DB)
- [ ] Integration test (optional, `@pytest.mark.integration`): real query against ingested corpus — deferred (covered manually by the Phase 8 smoke harness, `backend/scripts/smoke_questions.py`)
- [x] Verify: test queries from [brief](brief.md) return relevant chunks — confirmed via Phase 8 smoke test (9/10 grounded with on-topic citations)

---

## Phase 6 — LLM agent & grounding

Goal: grounded answers with enforced citations — the core product contract.

- [x] `assistant/instructions.md` — product contract (cite everything, refuse to invent, no stock picks)
- [x] PydanticAI agent (`gemini-2.5-flash-lite`) with typed deps (`DocumentAgentDeps`) and output (`AgentReply` → assembled `GroundedAnswer`)
- [x] Agent tools: `search_filings`, `read_chunk`, `read_surrounding_chunks`
- [x] `chat/orchestrator.py` — one turn: agent (retrieves via tools) → validate → stream → persist
- [x] `grounding/validator.py` — every citation maps to a retrieved passage; fail closed on violation
- [x] `chat/streaming.py` — AI SDK-compatible stream (text deltas + citation metadata parts)
- [x] Persist `message_citations` linked to assistant messages
- [x] Unit tests: citation validation, grounding enforcement, streaming frames, orchestrator
- [x] Verify against [brief example questions](brief.md#example-analyst-questions) — done via Phase 8 smoke test ([pilot-readiness](pilot-readiness.md)):
  - [x] Answers cite specific filings (and pages where ingested — many chunks lack page metadata)
  - [ ] Under-specified questions get "not enough evidence" responses — refusal path confirmed via Q10, but a dedicated under-specified query was not smoke-tested
  - [x] Question 10 (generative AI margins) refuses to infer beyond filings

---

## Phase 7 — Trust UI (citations & source passages)

**Goal:** analysts can verify every claim in one click — this is what makes the product usable.

- [x] Citation chips/links on assistant messages (company, filing type, date, page/section)
- [x] Source passage panel — show underlying excerpt for selected citation
- [x] Empty states (no threads, no corpus match)
- [x] Error states (auth expired, retrieval failure, grounding failure, network/CORS)
- [x] Loading/streaming status during assistant run
- [x] Verify: click a citation → see the exact passage from the filing

---

## Phase 8 — Pilot readiness

**Goal:** 5 senior analysts can use it for a week and report ≥3 hours saved per analyst per week.

- [x] README "Running locally" section — copy-paste commands for backend + frontend + env vars
- [x] Seed or document how to ingest/update the corpus
- [x] Smoke-test all 10 example questions from the client brief — 9/10 grounded; Q6 (5-company sweep) is a known limitation. See [pilot-readiness](pilot-readiness.md).
- [x] Confirm chat history persists across sessions — live persist→reload round-trip verified
- [x] Confirm ~40-user scale assumptions (no hardcoded single-user shortcuts) — audited, see [pilot-readiness](pilot-readiness.md)
- [x] Basic structured logging on backend (`structlog`) for debugging failed turns
- [x] Review latency: streaming starts within a few seconds for typical queries — **not met**: TTFT is 13–80s by design (grounding before streaming). Documented as a known limitation in [pilot-readiness](pilot-readiness.md).

---

## Phase 9 — Deployment (Railway)

- [ ] Railway: backend service (Uvicorn, env vars, `ALLOWED_ORIGINS`)
- [ ] Railway: frontend service (Vite build, `VITE_*` env vars at build time)
- [ ] Supabase: re-enable email confirmation for production if disabled during dev
- [ ] Run `alembic upgrade head` against production Supabase (direct connection)
- [ ] Run ingestion against production database
- [ ] End-to-end test on deployed URLs with a real Driftwood-style email account

---

## Appendix — Quick reference

**Run backend locally:**
```bash
cd backend && uv run uvicorn app.main:app --reload
```

**Run frontend locally:**
```bash
cd frontend && pnpm dev
```

**Add a new backend dep:**
```bash
cd backend && uv add <package>
```

**Run migrations:**
```bash
cd backend && uv run alembic upgrade head
```

**Generate a new migration after editing models.py:**
```bash
cd backend && uv run alembic revision --autogenerate -m "describe the change"
```

**Run backend tests:**
```bash
cd backend && uv run pytest -m "not integration"
cd backend && uv run pytest -m integration   # needs live creds
```

**Run ingest pipeline** (four idempotent steps; download/convert from repo root, load/chunk from `backend/`):
```bash
uv run data/download.py                          # 1. fetch 10-Ks from SEC EDGAR (edit USER_AGENT first)
uv run data/convert.py                           # 2. HTM -> Markdown
cd backend && uv run python ingest/load_source_documents.py  # 3. load source_documents
uv run python ingest/chunk_documents.py          # 4. chunk + embed into document_chunks
```

**Type-check frontend:**
```bash
cd frontend && pnpm tsc --noEmit
```
