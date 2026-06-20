"""demo_usage — per-user lifetime token budget + monthly demo slotting

Creates the `demo_usage` table that backs Phase B cost controls: a lifetime
token total per user and the month they were last active (for the global
"N demos/month" cap). Server-managed — the backend (table owner) reads/writes it
and bypasses RLS; a deny-all policy keeps any Supabase API client out.

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-20 12:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_usage",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "total_tokens", sa.BigInteger(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column(
            "total_requests", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
        sa.Column("last_active_month", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    # The monthly demo count is `count(*) where last_active_month = current month`.
    op.create_index(
        "ix_demo_usage_last_active_month", "demo_usage", ["last_active_month"]
    )

    # Server-managed table: only the backend (table owner, which bypasses RLS)
    # touches it. Deny-all keeps any authenticated PostgREST client from reading it.
    op.execute("alter table demo_usage enable row level security")
    op.execute(
        "create policy demo_usage_no_client on demo_usage "
        "for all using (false) with check (false)"
    )


def downgrade() -> None:
    op.drop_table("demo_usage")
