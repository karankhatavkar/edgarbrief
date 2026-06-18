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
- [ ] Integration test (optional, `@pytest.mark.integration`): real query against ingested corpus — deferred
- [ ] Verify: test queries from [client-brief](client-brief.md) return relevant chunks — deferred to Phase 8 (chat endpoint)

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
- [ ] Verify against [client-brief example questions](client-brief.md#example-analyst-questions) — deferred (needs live Gemini + Supabase):
  - [ ] Answers cite specific filings and pages
  - [ ] Under-specified questions get "not enough evidence" responses
  - [ ] Question 10 (generative AI margins) refuses to infer beyond filings

---

## Phase 7 — Chat persistence

**Goal:** chat threads and messages are durably stored in Supabase.

- [ ] Create `backend/app/database/chats.py`:
  - `create_thread(admin_client, user_id, title) → ChatThread`
  - `get_thread(client, thread_id, user_id) → ChatThread | None`
  - `list_threads(client, user_id) → list[ChatThread]`
  - `get_messages(client, thread_id) → list[ChatMessage]`
  - `save_user_message(client, thread_id, content) → ChatMessage`
  - `save_assistant_message(admin_client, thread_id, answer: GroundedAnswer) → ChatMessage` — saves message + citation rows
- [ ] Write `backend/tests/database/test_chats.py` — unit tests with mocked Supabase client

---

## Phase 8 — Chat streaming endpoint

**Goal:** `POST /chat/stream` receives a user message, runs the full RAG turn, and streams the answer back in AI SDK wire format.

- [ ] Create `backend/app/chat/messages.py` — convert AI SDK UI message format ↔ internal `ChatMessage` Pydantic models
- [ ] Create `backend/app/chat/streaming.py` — async generator that emits AI SDK SSE events:
  - `0:"text delta"` — partial text as it streams
  - `8:[{citation}]` — citation/source metadata parts once available
  - `3:"error message"` — on auth failure, grounding failure, LLM error
  - `d:{finishReason, usage}` — finish event
- [ ] Create `backend/app/chat/orchestrator.py` — `run_chat_turn(user, thread_id, messages, retriever, validator)`:
  1. Verify thread belongs to user
  2. Retrieve relevant passages
  3. Run PydanticAI agent
  4. Validate grounding
  5. Stream answer
  6. Persist messages and citations
- [ ] Create `backend/app/api/chat.py`:
  - `POST /chat/stream` — authenticated, calls orchestrator, returns `StreamingResponse` with `text/event-stream`
  - `GET /threads` — list user's threads
  - `POST /threads` — create new thread
  - `GET /threads/{thread_id}/messages` — load message history for a thread
- [ ] Wire all routers into `main.py`
- [ ] Manual test with curl: `curl -N -X POST http://localhost:8000/chat/stream -H "Authorization: Bearer <token>" -H "Content-Type: application/json" -d '{"threadId":"...","messages":[{"role":"user","content":"What was Apple revenue in 2024?"}]}'`
- [ ] Verify SSE stream arrives and contains text deltas + citation parts

---

## Phase 8 — Frontend scaffold

**Goal:** Vite React TypeScript SPA boots, config validated, router in place.

- [ ] Initialize Vite project: `pnpm create vite frontend --template react-ts` (if not already done)
- [ ] Install deps:
  - `pnpm add react-router-dom @supabase/supabase-js`
  - `pnpm add ai @ai-sdk/react` (Vercel AI SDK)
  - `pnpm add tailwindcss @tailwindcss/vite`
  - `pnpm dlx shadcn@latest init`
- [ ] Add shadcn primitives needed: `pnpm dlx shadcn@latest add button input card scroll-area separator`
- [ ] Set up Tailwind: `tailwind.config.ts`, `src/index.css` with Tailwind directives + CSS variables for shadcn theme
- [ ] Create `frontend/src/lib/env.ts` — validate `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` at module load; throw if missing
- [ ] Create `frontend/src/lib/supabase.ts` — single `createClient` call using env vars
- [ ] Create `frontend/src/lib/http.ts` — `apiFetch(path, options)` wrapper:
  - Prepends `env.VITE_API_BASE_URL`
  - Injects `Authorization: Bearer <supabase_access_token>` automatically
  - 30s timeout via `AbortController`
  - On non-OK response: throws typed `ApiError { status, message, isNetworkError }`
- [ ] Create `frontend/src/lib/api.ts` — product API calls:
  - `listThreads() → Thread[]`
  - `createThread(title: string) → Thread`
  - `getMessages(threadId: string) → Message[]`
- [ ] Create `frontend/src/App.tsx` — React Router routes:
  - `/login` → `LoginPage`
  - `/signup` → `SignupPage`
  - `/` → `ChatPage` (protected)
  - `/thread/:threadId` → `ChatPage` (protected)
- [ ] Confirm `pnpm dev` starts without errors and routes render

---

## Phase 9 — Frontend auth

**Goal:** user can sign up, log in, and be redirected to the chat. Unauthenticated routes redirect to `/login`.

- [ ] Create `frontend/src/lib/auth.ts` — `useSession()` hook that subscribes to `supabase.auth.onAuthStateChange` and returns `{ session, loading }`
- [ ] Create `frontend/src/components/ProtectedRoute.tsx` — if `loading` show spinner; if no session redirect to `/login`; otherwise render children
- [ ] Create `frontend/src/pages/auth/LoginPage.tsx`:
  - Email + password form
  - `supabase.auth.signInWithPassword()`
  - On success: navigate to `/`
  - On error: show inline error message
- [ ] Create `frontend/src/pages/auth/SignupPage.tsx`:
  - Email + password + confirm password form
  - `supabase.auth.signUp()`
  - On success: navigate to `/` (or show "check your email" if confirmation is enabled)
- [ ] Add sign-out button (calls `supabase.auth.signOut()`, redirects to `/login`)
- [ ] Manual test: sign up → receive session → see chat page; sign out → redirected to login; try accessing `/` without auth → redirected to login

---

## Phase 10 — Frontend chat UI

**Goal:** user can start a thread, ask a question, and see a streamed grounded answer.

- [ ] Create `frontend/src/pages/chat/ChatPage.tsx`:
  - Left sidebar: list of threads (from `api.listThreads()`) + "New chat" button
  - Main area: `<ChatWindow>` for the selected thread (or empty state if no thread selected)
- [ ] Create `frontend/src/components/chat/ChatWindow.tsx`:
  - Initialize `useChat` from `@ai-sdk/react` with:
    ```ts
    transport: new DefaultChatTransport({
      api: `${env.VITE_API_BASE_URL}/chat/stream`,
      headers: async () => ({
        Authorization: `Bearer ${(await supabase.auth.getSession()).data.session?.access_token}`,
      }),
    })
    ```
  - Fetch prior messages via `api.getMessages(threadId)` and pass as `initialMessages`
  - Render `<MessageBubble>` for each message
  - `<ChatInput>` at the bottom with send button
- [ ] Create `frontend/src/components/chat/MessageBubble.tsx` — render user vs assistant messages; assistant messages: Markdown-rendered text + citation cards below
- [ ] Create `frontend/src/components/chat/ChatInput.tsx` — textarea (Shift+Enter for newline, Enter to send), disabled while streaming, shows spinner during `status === 'streaming'`
- [ ] Handle new thread creation: "New chat" → `api.createThread("New chat")` → navigate to `/thread/:id`
- [ ] Auto-update thread title from first user message (PATCH `/threads/:id` with first 60 chars of query)
- [ ] Manual test: ask "What was Apple revenue in 2024?" — verify streamed text appears incrementally

---

## Phase 12 — Citation & source passage UI

**Goal:** analyst can see exactly which filing passages back each claim.

- [ ] Parse citation data parts from AI SDK stream (the `8:` event type carries structured citation JSON)
- [ ] Create `frontend/src/components/chat/CitationCard.tsx`:
  - Shows: company name, filing type + date, page/section
  - Clicking expands to show excerpt text
  - Styled to look like a footnote reference (numbered superscript inline in answer text)
- [ ] Create `frontend/src/components/chat/SourcePanel.tsx`:
  - Collapsible sidebar or inline panel listing all citations for the current message
  - Each citation: company, filing, date, section, full excerpt
- [ ] Inline superscript citation numbers in `MessageBubble` (e.g., `[1]`, `[2]`) linked to their `CitationCard`
- [ ] Manual test: verify citation cards show correct metadata and excerpt from actual filing

---

## Phase 13 — Error states & empty states

**Goal:** every failure mode has a clear, friendly UI response.

- [ ] Auth errors (401 from backend) → clear session, redirect to `/login` with "Session expired" message
- [ ] Forbidden (403) → show "You don't have access to this thread"
- [ ] Grounding failure (backend returns error event) → show "The corpus doesn't contain enough evidence to answer this question" in the chat
- [ ] LLM / Supabase errors (502, 500) → show "Something went wrong — please try again" with retry button
- [ ] Network error (`isNetworkError` flag) → show "Connection lost — check your network"
- [ ] Empty chat state (no threads) → show example analyst questions from `brief.md` as prompt chips
- [ ] Loading skeleton for thread list and message history (shimmer placeholder)
- [ ] Message streaming: show typing indicator while `status === 'streaming'`

---

## Phase 14 — Backend tests & hardening

**Goal:** all critical paths are covered by tests; the suite is fast and runs without network by default.

- [ ] `pytest -m "not integration"` passes with no network/DB calls
- [ ] Tests exist for:
  - Auth dependency (mocked Supabase)
  - Grounding validator (pure Python)
  - RRF fusion (pure Python)
  - Chunking logic (pure Python)
  - HTML → Markdown extraction (pure Python)
  - Chat persistence helpers (mocked Supabase client)
  - Streaming event format (unit test the event serialization)
- [ ] Integration tests (marked `@pytest.mark.integration`) cover:
  - Retrieval against live Supabase
  - Full chat turn against live Gemini + Supabase
- [ ] `ruff check backend/` passes with no errors
- [ ] `ruff format backend/` applied

---

## Phase 15 — Frontend quality

- [ ] `pnpm tsc --noEmit` passes with no errors (strict mode)
- [ ] `pnpm lint` (ESLint) passes with no errors
- [ ] Manual regression test on golden path:
  1. Sign up with a new email
  2. Start a new chat thread
  3. Ask: "Across Apple's 2021–2025 10-Ks, how did the revenue mix between iPhone, Services, Mac, iPad, and Wearables change?"
  4. Verify: streamed answer appears, citations display correct company/filing/section, clicking a citation shows the excerpt
  5. Refresh the page — prior messages load from Supabase
  6. Sign out → redirected to login

---

## Phase 16 — Railway deployment

**Goal:** production app running on Railway, accessible from browser, backed by Supabase.

- [ ] Create Railway project with two services: `backend` and `frontend`
- [ ] Backend service:
  - Root: `backend/`
  - Build command: `uv sync`
  - Start command: `uv run uvicorn app.main:app --host 0.0.0.0 --port $PORT`
  - Set all env vars: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_EMBEDDING_MODEL`, `GEMINI_EMBEDDING_DIMENSIONS`, `ALLOWED_ORIGINS` (Railway frontend domain)
- [ ] Frontend service:
  - Root: `frontend/`
  - Build command: `pnpm install && pnpm build`
  - Start: serve `dist/` as static site
  - Set env vars: `VITE_API_BASE_URL` (Railway backend domain), `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
- [ ] Add Railway backend domain to Supabase Auth → allowed redirect URLs
- [ ] End-to-end production smoke test: open Railway frontend URL, log in, ask a question, verify answer + citations

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

**Run ingest pipeline:**
```bash
cd backend && uv run python -m ingest.run
```

**Type-check frontend:**
```bash
cd frontend && pnpm tsc --noEmit
```
