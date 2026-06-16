"""SQLAlchemy models — the source of truth for the database schema.

One module per table. Importing this package registers every model on the
shared declarative `Base`, so Alembic autogenerate and string-based
relationship resolution see the full schema. Import models from here, e.g.
`from app.database.models import DocumentChunk`.
"""

from app.database.models.base import Base, TimestampMixin, uuid_pk
from app.database.models.chat_message import ChatMessage
from app.database.models.chat_thread import ChatThread
from app.database.models.document_chunk import DocumentChunk
from app.database.models.message_citation import MessageCitation
from app.database.models.source_document import SourceDocument
from app.database.models.user import User

__all__ = [
    "Base",
    "TimestampMixin",
    "uuid_pk",
    "User",
    "SourceDocument",
    "DocumentChunk",
    "ChatThread",
    "ChatMessage",
    "MessageCitation",
]
