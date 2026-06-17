"""source_documents: add report_date, markdown, word_count

report_date  — fiscal period end date (distinct from filing_date which is the
               SEC submission date). Lets the UI say "FY2024 ending Sep 28"
               instead of just the year integer.
markdown     — full converted markdown text of the filing; stored here so
               downstream chunking/re-indexing doesn't need to re-read files.
word_count   — word count derived from markdown at ingest time; cheap metadata
               for display/filtering without loading the full text.

All three are nullable so this migration is safe against an already-populated
table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-17 18:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("report_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("markdown", sa.Text(), nullable=True),
    )
    op.add_column(
        "source_documents",
        sa.Column("word_count", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("source_documents", "word_count")
    op.drop_column("source_documents", "markdown")
    op.drop_column("source_documents", "report_date")
