"""Shared declarative base and column helpers for the ORM models.

Postgres/Supabase-specific objects that autogenerate can't express
(the `vector` extension, HNSW + GIN indexes, RLS policies) live in the
Alembic migrations. Everything declarative — columns, the `vector`
embedding, and the generated `tsvector` — is defined in the per-table
modules in this package.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
