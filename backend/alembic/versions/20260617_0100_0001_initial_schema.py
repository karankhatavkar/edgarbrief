"""initial schema

Creates the full schema: the pgvector extension, all six tables, the
vector(768) embedding column, the generated tsvector column on chunks,
the HNSW (vector) and GIN (full-text) indexes, and RLS policies that scope
chat data to its owning user. RLS is enforced for clients reaching Postgres
through Supabase's auth'd API; the backend connects as table owner and is
not restricted by it.

Revision ID: 0001
Revises:
Create Date: 2026-06-17 01:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

EMBEDDING_DIM = 768


def upgrade() -> None:
    op.execute("create extension if not exists vector")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "source_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ticker", sa.String(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("cik", sa.String(), nullable=False),
        sa.Column("filing_type", sa.String(), nullable=False),
        sa.Column("filing_date", sa.Date(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("accession_number", sa.String(), nullable=False),
        sa.Column("source_url", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("accession_number"),
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False),
        sa.Column("section", sa.String(), nullable=True),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', content)", persisted=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["document_id"], ["source_documents.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "chunk_index"),
    )
    op.create_index(
        "ix_document_chunks_document_id", "document_chunks", ["document_id"]
    )
    # Approximate nearest-neighbour search over embeddings (cosine distance).
    op.create_index(
        "ix_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    # Full-text keyword retrieval over the generated tsvector.
    op.create_index(
        "ix_document_chunks_search_vector",
        "document_chunks",
        ["search_vector"],
        postgresql_using="gin",
    )

    op.create_table(
        "chat_threads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_threads_user_id", "chat_threads", ["user_id"])

    op.create_table(
        "chat_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("thread_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["thread_id"], ["chat_threads.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_messages_thread_id", "chat_messages", ["thread_id"])

    op.create_table(
        "message_citations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("claim_text", sa.Text(), nullable=False),
        sa.Column("passage_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["chat_messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["chunk_id"], ["document_chunks.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_message_citations_message_id", "message_citations", ["message_id"]
    )

    _enable_rls()


def _enable_rls() -> None:
    """Row-level security: each user reaches only their own chat data.

    The shared filing corpus (source_documents, document_chunks) is readable
    by any authenticated client; only the backend (table owner) writes to it.
    """
    op.execute("alter table users enable row level security")
    op.execute(
        "create policy users_select_own on users "
        "for select using (auth.uid() = id)"
    )
    op.execute(
        "create policy users_update_own on users "
        "for update using (auth.uid() = id)"
    )

    op.execute("alter table chat_threads enable row level security")
    op.execute(
        "create policy chat_threads_owner on chat_threads "
        "for all using (auth.uid() = user_id) "
        "with check (auth.uid() = user_id)"
    )

    op.execute("alter table chat_messages enable row level security")
    op.execute(
        "create policy chat_messages_owner on chat_messages for all "
        "using (exists (select 1 from chat_threads t "
        "where t.id = chat_messages.thread_id and t.user_id = auth.uid())) "
        "with check (exists (select 1 from chat_threads t "
        "where t.id = chat_messages.thread_id and t.user_id = auth.uid()))"
    )

    op.execute("alter table message_citations enable row level security")
    op.execute(
        "create policy message_citations_owner on message_citations for all "
        "using (exists (select 1 from chat_messages m "
        "join chat_threads t on t.id = m.thread_id "
        "where m.id = message_citations.message_id and t.user_id = auth.uid())) "
        "with check (exists (select 1 from chat_messages m "
        "join chat_threads t on t.id = m.thread_id "
        "where m.id = message_citations.message_id and t.user_id = auth.uid()))"
    )

    op.execute("alter table source_documents enable row level security")
    op.execute(
        "create policy source_documents_read on source_documents "
        "for select to authenticated using (true)"
    )
    op.execute("alter table document_chunks enable row level security")
    op.execute(
        "create policy document_chunks_read on document_chunks "
        "for select to authenticated using (true)"
    )


def downgrade() -> None:
    op.drop_table("message_citations")
    op.drop_table("chat_messages")
    op.drop_table("chat_threads")
    op.drop_table("document_chunks")
    op.drop_table("source_documents")
    op.drop_table("users")
    op.execute("drop extension if exists vector")
