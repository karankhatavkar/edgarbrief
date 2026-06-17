"""server-side gen_random_uuid() default on uuid primary keys

The ORM models declare ``id`` with a SQLAlchemy ``default=uuid.uuid4``, which
only fires on ORM inserts. The data layer writes through the Supabase REST
client (PostgREST), which omits ``id`` from the payload, so Postgres had no
value and no default for it — every insert failed with a NOT NULL violation on
``id``. This adds the missing server-side default to the tables that generate
their own primary key. ``users`` is excluded: its ``id`` mirrors
``auth.users.id`` and is always supplied explicitly.

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-17 17:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = (
    "chat_threads",
    "chat_messages",
    "message_citations",
    "source_documents",
    "document_chunks",
)


def upgrade() -> None:
    for table in _TABLES:
        op.execute(f"alter table {table} alter column id set default gen_random_uuid()")


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"alter table {table} alter column id drop default")
