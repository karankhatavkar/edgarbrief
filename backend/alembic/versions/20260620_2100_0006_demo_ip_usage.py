"""demo_ip_usage — per-IP monthly count of distinct demo users started

A soft, additive abuse brake beside the per-user budget and global monthly cap:
counts how many distinct anonymous demo users one client IP has started in a
calendar month, so wiping localStorage / going incognito from one machine can't
mint unlimited fresh per-user budgets. Grain is (ip, month) so it resets on the
1st. Server-managed — the backend (table owner) reads/writes it and bypasses RLS;
a deny-all policy keeps any Supabase API client out.

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-20 21:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "demo_ip_usage",
        sa.Column("ip", sa.String(length=45), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column(
            "user_count", sa.Integer(), server_default=sa.text("0"), nullable=False
        ),
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
        sa.PrimaryKeyConstraint("ip", "month"),
    )

    # Server-managed table: only the backend (table owner, which bypasses RLS)
    # touches it. Deny-all keeps any authenticated PostgREST client from reading it.
    op.execute("alter table demo_ip_usage enable row level security")
    op.execute(
        "create policy demo_ip_usage_no_client on demo_ip_usage "
        "for all using (false) with check (false)"
    )


def downgrade() -> None:
    op.drop_table("demo_ip_usage")
