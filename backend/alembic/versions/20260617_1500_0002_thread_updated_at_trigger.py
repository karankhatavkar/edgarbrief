"""bump chat_threads.updated_at when a message is inserted

Message writes go through the Supabase REST client, not the ORM, so the model's
application-side ``onupdate=func.now()`` never fires, and inserting a message
doesn't otherwise touch its thread. Without this, ``list_threads`` ordering by
``updated_at`` reflects creation/title-edit time, not real conversation
activity. A trigger keeps ``updated_at`` in sync on every message insert.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-17 15:00
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        create or replace function bump_thread_updated_at()
        returns trigger as $$
        begin
            update chat_threads set updated_at = now() where id = new.thread_id;
            return new;
        end;
        $$ language plpgsql
        """
    )
    op.execute(
        "create trigger chat_messages_bump_thread "
        "after insert on chat_messages "
        "for each row execute function bump_thread_updated_at()"
    )


def downgrade() -> None:
    op.execute(
        "drop trigger if exists chat_messages_bump_thread on chat_messages"
    )
    op.execute("drop function if exists bump_thread_updated_at()")
