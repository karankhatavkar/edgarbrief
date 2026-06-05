# Backend setup

This project uses a separate Python + FastAPI backend because the server is responsible for AI and document-processing work, not just basic web CRUD. Python gives us the strongest ecosystem for ingestion, chunking, embeddings, retrieval, evaluation, and LLM workflows. Keeping this logic behind a dedicated API also keeps the frontend focused on the user experience while the backend owns data access, orchestration, and grounding.

## Init (from empty `backend/`)

```bash
cd backend
uv sync
uv add fastapi uvicorn pydantic pydantic-settings httpx structlog openai supabase pydantic-ai sqlalchemy alembic "psycopg[binary]" pgvector
uv add --dev pytest ruff
```

## Database migrations

Alembic owns database schema changes for this project. SQLAlchemy models describe the app tables, and Alembic migrations apply those changes to Supabase Postgres.

Initialize Alembic once from `backend/`:

```bash
uv run alembic init alembic
```

Configure `alembic/env.py` to import the app's SQLAlchemy metadata and read the direct database URL from `app.config.settings`. Use the direct/session Supabase database connection, not the transaction pooler URL, for migrations.

Create a migration after changing SQLAlchemy models:

```bash
uv run alembic revision --autogenerate -m "add document tables"
```

Always review the generated migration. Add explicit operations for Supabase/Postgres features that autogenerate cannot reliably infer:

- `create extension if not exists vector`
- `vector(1536)` columns
- generated `tsvector` columns
- HNSW and GIN indexes
- RLS enablement and policies

Apply migrations:

```bash
uv run alembic upgrade head
```

## Run

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

## Sample SEC data

From the repo root (stdlib-only script, no backend env needed):

```bash
uv run data/download.py
```
