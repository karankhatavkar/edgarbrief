"""Query-assembly tests: compile each statement and assert its SQL shape.

A capturing fake session records the statement the function builds, which is
then compiled against the postgres dialect — no database, no network.
"""

import asyncio
import uuid
from types import SimpleNamespace

from sqlalchemy.dialects import postgresql

from app.retrieval import queries


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class CapturingSession:
    """Stand-in for AsyncSession that records statements and returns canned rows."""

    def __init__(self, rows=()):
        self.statements = []
        self._rows = list(rows)

    async def scalars(self, stmt):
        self.statements.append(stmt)
        return _Result(self._rows)


def _sql(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect())).lower()


def test_vector_search_orders_by_cosine_distance_with_limit():
    session = CapturingSession()
    asyncio.run(queries.vector_search(session, [0.0] * 768, limit=20))
    sql = _sql(session.statements[0])
    assert "<=>" in sql  # pgvector cosine-distance operator
    assert "order by" in sql
    assert "limit" in sql


def test_fulltext_search_matches_ranks_and_limits():
    session = CapturingSession()
    asyncio.run(queries.fulltext_search(session, "data center demand", limit=20))
    sql = _sql(session.statements[0])
    assert "websearch_to_tsquery" in sql
    assert "@@" in sql
    assert "ts_rank" in sql
    assert "limit" in sql


def test_fetch_neighbors_short_circuits_without_anchors():
    session = CapturingSession()
    result = asyncio.run(queries.fetch_neighbors(session, [], window=1))
    assert result == []
    assert session.statements == []  # no query issued


def test_fetch_neighbors_looks_up_adjacent_index_pairs():
    session = CapturingSession()
    anchor = SimpleNamespace(document_id=uuid.uuid4(), chunk_index=5)
    asyncio.run(queries.fetch_neighbors(session, [anchor], window=1))
    sql = _sql(session.statements[0])
    # composite (document_id, chunk_index) IN (...) lookup
    assert "document_id" in sql
    assert "chunk_index" in sql
    assert "in (" in sql
