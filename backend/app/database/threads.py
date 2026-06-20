"""Typed query helpers for chat threads and messages."""

import uuid
from dataclasses import dataclass
from datetime import datetime

from supabase import AsyncClient


@dataclass
class ThreadRow:
    id: uuid.UUID
    user_id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime


@dataclass
class MessageRow:
    id: uuid.UUID
    thread_id: uuid.UUID
    role: str
    content: str
    created_at: datetime


async def ensure_user(client: AsyncClient, user_id: uuid.UUID, email: str | None) -> None:
    """Upsert the user row so FK constraints on chat_threads are satisfied.

    Must be called with the service-role client (RLS bypassed) since the users
    table only allows users to select/update their own row, not insert.
    """
    await (
        client.table("users")
        .upsert({"id": str(user_id), "email": email}, on_conflict="id")
        .execute()
    )


async def list_threads(client: AsyncClient) -> list[ThreadRow]:
    """Return all threads visible to this client, newest first.

    With a user_client, RLS scopes the result to the caller automatically.
    """
    result = (
        await client.table("chat_threads")
        .select("*")
        .order("updated_at", desc=True)
        .execute()
    )
    return [_parse_thread(row) for row in result.data]


async def create_thread(
    client: AsyncClient, user_id: uuid.UUID, title: str
) -> ThreadRow:
    result = (
        await client.table("chat_threads")
        .insert({"user_id": str(user_id), "title": title})
        .execute()
    )
    return _parse_thread(result.data[0])


async def update_thread_title(
    client: AsyncClient, thread_id: uuid.UUID, title: str
) -> None:
    await (
        client.table("chat_threads")
        .update({"title": title})
        .eq("id", str(thread_id))
        .execute()
    )


async def count_messages(client: AsyncClient, thread_id: uuid.UUID) -> int:
    result = (
        await client.table("chat_messages")
        .select("id", count="exact", head=True)
        .eq("thread_id", str(thread_id))
        .execute()
    )
    return result.count or 0


async def get_thread(
    client: AsyncClient, thread_id: uuid.UUID
) -> ThreadRow | None:
    result = (
        await client.table("chat_threads")
        .select("*")
        .eq("id", str(thread_id))
        .execute()
    )
    if not result.data:
        return None
    return _parse_thread(result.data[0])


async def save_message(
    client: AsyncClient, thread_id: uuid.UUID, role: str, content: str
) -> MessageRow:
    result = (
        await client.table("chat_messages")
        .insert({"thread_id": str(thread_id), "role": role, "content": content})
        .execute()
    )
    return _parse_message(result.data[0])


async def save_assistant_message(
    client: AsyncClient,
    thread_id: uuid.UUID,
    answer: str,
    citation_rows: list[dict],
) -> MessageRow:
    """Persist an assistant message and its citation rows.

    ``citation_rows`` carry ``chunk_id``/``claim_text``/``passage_index``; the
    new message's id is filled in here so callers stay free of message identity.
    """
    message = await save_message(client, thread_id, "assistant", answer)
    rows = [{**row, "message_id": str(message.id)} for row in citation_rows]
    if rows:
        await client.table("message_citations").insert(rows).execute()
    return message


async def list_messages(
    client: AsyncClient, thread_id: uuid.UUID
) -> list[MessageRow]:
    result = (
        await client.table("chat_messages")
        .select("*")
        .eq("thread_id", str(thread_id))
        .order("created_at")
        .execute()
    )
    return [_parse_message(row) for row in result.data]


async def list_message_citations(
    client: AsyncClient, message_ids: list[uuid.UUID]
) -> list[dict]:
    """Return citation rows for the given messages, newest claim order preserved.

    Each row embeds its source chunk and that chunk's filing, so the caller can
    rebuild the same ``SourcePassage`` shape the live stream emits. Ordered by
    ``passage_index`` to match the numbering shown while streaming.

    Reads corpus tables that aren't RLS-readable by the user client, so callers
    pass the service client — thread ownership must already be enforced.
    """
    if not message_ids:
        return []
    result = (
        await client.table("message_citations")
        .select(
            "message_id, passage_index, "
            "document_chunks(id, section, page, content, "
            "source_documents(ticker, company, fiscal_year, filing_type, "
            "filing_date, source_url))"
        )
        .in_("message_id", [str(m) for m in message_ids])
        .order("passage_index")
        .execute()
    )
    return result.data


def _parse_thread(row: dict) -> ThreadRow:
    return ThreadRow(
        id=uuid.UUID(row["id"]),
        user_id=uuid.UUID(row["user_id"]),
        title=row["title"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _parse_message(row: dict) -> MessageRow:
    return MessageRow(
        id=uuid.UUID(row["id"]),
        thread_id=uuid.UUID(row["thread_id"]),
        role=row["role"],
        content=row["content"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
