"""Async SQLAlchemy engine for request-path database access.

Retrieval (and later request-path queries) need pgvector distance ordering,
which PostgREST can't express — so they talk to Postgres directly through
SQLAlchemy over psycopg3's async driver rather than the Supabase client.

Use ``settings.database_url`` (the direct/session connection Alembic also uses),
never the Supabase transaction pooler: psycopg3's prepared statements break
under pgbouncer transaction mode.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings


def _async_db_url() -> str:
    url = str(settings.database_url)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


# Keep a small pool of warm connections so demo traffic doesn't pay the
# ~2-3s cold TLS+auth handshake to Supabase on every request. pool_pre_ping
# discards connections the server/pooler closed while idle; pool_recycle
# refreshes them before Supabase's idle timeout can.
engine = create_async_engine(
    _async_db_url(),
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=5,
    pool_recycle=1800,
)

# expire_on_commit=False keeps loaded ORM objects usable after the session closes.
async_session = async_sessionmaker(engine, expire_on_commit=False)
