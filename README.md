# EdgarBrief

An AI assistant that lets equity research analysts query a corpus of SEC filings in plain English and get sourced, citable answers.

## The problem

Analysts at independent equity research boutiques spend roughly half their week doing document intake — reading 10-Ks and 10-Qs before they can produce any original analysis. EdgarBrief eliminates that bottleneck so analysts can skip straight to insight.

Full brief: [docs/brief.md](docs/brief.md)

## Stack

| Layer              | Choice                                               |
| ------------------ | ---------------------------------------------------- |
| Backend            | Python + FastAPI                                     |
| Frontend           | Vite + React SPA + TypeScript                        |
| Database           | Supabase Postgres (users, chats, documents, chunks)  |
| Migrations         | SQLAlchemy models + Alembic                          |
| Retrieval          | Supabase `pgvector` + Postgres full-text search      |
| Auth               | Supabase Auth (email only)                           |
| Hosting            | Railway                                              |
| LLM + embeddings   | Google Gemini                                        |

## Repo layout

```text
document-copilot/
├── CLAUDE.md           # agent instructions (read first)
├── README.md           # this file
├── data/               # local corpus + download script (payloads gitignored)
├── docs/
│   └── brief.md        # problem statement
├── backend/            # FastAPI service
└── frontend/           # React SPA (Vite)
```

## Prerequisites

Install these before setting up `backend/` or `frontend/`:

| Tool | Version | Used for | Install |
| ---- | ------- | -------- | ------- |
| [Python](https://www.python.org/downloads/) | 3.12+ | Backend runtime | OS package manager or python.org |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | latest | Backend deps + `data/download.py` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| [Node.js](https://nodejs.org/) | 20+ (LTS) | Frontend toolchain | nodejs.org or `nvm install --lts` |
| [pnpm](https://pnpm.io/installation) | latest | Frontend package manager | `corepack enable && corepack prepare pnpm@latest --activate` |

You also need accounts/keys for external services once the app is wired up. Start with [docs/guides/supabase-setup.md](docs/guides/supabase-setup.md) (account + project), then create a [Gemini API key](https://aistudio.google.com/app/apikey) when the LLM layer is wired up.

## Running locally

You need a [Supabase](docs/guides/supabase-setup.md) project and a
[Gemini API key](https://aistudio.google.com/app/apikey) first. Detailed setup
guides: [Supabase](docs/guides/supabase-setup.md) ·
[Backend](docs/guides/backend-setup.md) · [Frontend](docs/guides/frontend-setup.md).

### 1. Backend

```bash
cd backend
uv sync                              # install dependencies
cp .env.example .env                 # then fill in the values (table below)
uv run alembic upgrade head          # create the schema (uses direct DATABASE_URL)
uv run uvicorn app.main:app --reload # serves http://localhost:8000
```

Backend env vars (`backend/.env`) — all required unless noted; the service fails
fast on startup if a required one is missing:

| Var | What it is |
| --- | ---------- |
| `SUPABASE_URL` | Project URL (`https://<ref>.supabase.co`) |
| `SUPABASE_ANON_KEY` | Public anon key |
| `SUPABASE_SERVICE_ROLE_KEY` | Secret service-role key (backend-only writes) |
| `DATABASE_URL` | **Direct** Postgres connection (not the pooler) — used by Alembic + the app |
| `GEMINI_API_KEY` | Google Gemini API key |
| `GEMINI_CHAT_MODEL` | Optional, default `gemini-2.5-flash-lite` |
| `GEMINI_EMBEDDING_MODEL` | Optional, default `gemini-embedding-001` |
| `GEMINI_EMBEDDING_DIMENSIONS` | Optional, default `768` |
| `ALLOWED_ORIGINS` | JSON list of CORS origins, default `["http://localhost:5173"]` |
| `LOG_LEVEL` | Optional, default `INFO` |
| `LOG_JSON` | Optional, default `false`; set `true` in prod for JSON logs |

### 2. Frontend

```bash
cd frontend
cp .env.example .env   # then fill in the values (table below)
pnpm install
pnpm dev               # serves http://localhost:5173
```

Frontend env vars (`frontend/.env`) — only browser-safe public values:

| Var | What it is |
| --- | ---------- |
| `VITE_API_BASE_URL` | Backend URL, e.g. `http://localhost:8000` |
| `VITE_SUPABASE_URL` | Same as backend `SUPABASE_URL` |
| `VITE_SUPABASE_ANON_KEY` | Same as backend `SUPABASE_ANON_KEY` |

### 3. Seed the corpus

The corpus is loaded by four idempotent steps — re-running skips anything already
downloaded, converted, or ingested. Run the first two from the repo root, the last
two from `backend/`:

```bash
# 1. Download 10-Ks from SEC EDGAR (edit USER_AGENT at the top of the script first)
uv run data/download.py
# 2. Convert the filings HTM -> Markdown (see data/README.md for the pipeline)
uv run data/convert.py

cd backend
# 3. Load filings into source_documents
uv run python ingest/load_source_documents.py
# 4. Chunk + embed into document_chunks (calls Gemini; needs GEMINI_API_KEY)
uv run python ingest/chunk_documents.py
```

By default this loads the latest 5 10-K filings each for AAPL, MSFT, NVDA, AMZN, and
GOOGL (25 filings). Downloaded/converted payloads are gitignored; the `data/` folder
itself stays in git for the scripts and notes. See [data/README.md](data/README.md)
for the HTM→Markdown conversion details.
