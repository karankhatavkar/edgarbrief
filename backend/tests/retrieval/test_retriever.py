"""Orchestration tests for ``retrieve`` — fusion, neighbours, and metadata wiring.

The embedding call is monkeypatched and the session is faked, so this exercises
the retriever's own logic with no network or database.
"""

import asyncio
import uuid
from types import SimpleNamespace

from app.retrieval import retriever
from app.retrieval.retriever import RetrievedPassage, retrieve


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    """Returns canned scalars() batches in the order ``retrieve`` issues them:

    1) vector_search  2) fulltext_search  3) load_anchors  4) fetch_neighbors
    """

    def __init__(self, batches):
        self._batches = list(batches)
        self.calls = 0

    async def scalars(self, stmt):
        rows = self._batches[self.calls]
        self.calls += 1
        return _Result(rows)


def _chunk(document_id, chunk_index):
    return SimpleNamespace(
        id=uuid.uuid4(), document_id=document_id, chunk_index=chunk_index
    )


def _patch_embed(monkeypatch, sink=None):
    async def fake_embed(text):
        if sink is not None:
            sink["query"] = text
        return [0.0] * 768

    monkeypatch.setattr(retriever, "embed_query", fake_embed)


def test_retrieve_fuses_arms_attaches_neighbors_and_metadata(monkeypatch):
    d1, da, db, dc = (uuid.uuid4() for _ in range(4))
    c1 = _chunk(d1, 5)
    c2 = _chunk(da, 10)
    c3 = _chunk(db, 0)
    c4 = _chunk(dc, 3)

    vector_hits = [c1, c2, c3]  # ranks 0,1,2
    fulltext_hits = [c2, c4, c1]  # ranks 0,1,2
    # RRF(k=60): c2=1/61+1/62, c1=1/61+1/63, c4=1/62, c3=1/63  ->  c2, c1, c4, c3
    anchors = [c1, c2, c3, c4]

    nb_low = _chunk(da, 9)  # adjacent to c2 (idx 10)
    nb_high = _chunk(da, 11)  # adjacent to c2
    self_c2 = SimpleNamespace(id=c2.id, document_id=da, chunk_index=10)  # excluded: self
    foreign = _chunk(dc, 99)  # in c4's document but far outside the window
    neighbor_rows = [nb_high, nb_low, self_c2, foreign]

    session = FakeSession([vector_hits, fulltext_hits, anchors, neighbor_rows])

    seen: dict[str, str] = {}
    _patch_embed(monkeypatch, seen)

    passages = asyncio.run(retrieve(session, "iphone services revenue"))

    assert seen["query"] == "iphone services revenue"
    assert all(isinstance(p, RetrievedPassage) for p in passages)
    assert [p.chunk for p in passages] == [c2, c1, c4, c3]  # fused order

    scores = [p.score for p in passages]
    assert scores[0] > scores[1] > scores[2] > scores[3]

    # c2's neighbours: adjacent only, sorted by chunk_index, self excluded.
    assert passages[0].neighbors == [nb_low, nb_high]
    # The rest have nothing in-window.
    assert passages[1].neighbors == []
    assert passages[2].neighbors == []
    assert passages[3].neighbors == []


def test_retrieve_respects_top_k(monkeypatch):
    document_id = uuid.uuid4()
    hits = [_chunk(document_id, i) for i in range(5)]
    # vector=5 hits, fulltext=0, anchors=all, neighbours=none.
    session = FakeSession([hits, [], hits, []])
    _patch_embed(monkeypatch)

    passages = asyncio.run(retrieve(session, "q", top_k=3))
    assert len(passages) == 3
    assert [p.chunk for p in passages] == hits[:3]
