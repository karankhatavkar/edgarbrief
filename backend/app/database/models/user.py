"""`users` — public mirror of Supabase auth users."""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.database.models.chat_thread import ChatThread


class User(Base, TimestampMixin):
    """Public mirror of a Supabase `auth.users` row, keyed by the same id."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        # The FK to auth.users is enforced at DB level in the migration;
        # omitted here because SQLAlchemy cannot resolve cross-schema auth.* tables.
    )
    email: Mapped[str | None] = mapped_column(String)

    threads: Mapped[list["ChatThread"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
