"""Unit tests for assembling the grounded answer from the retrieved set."""

from app.assistant.outputs import AgentReply, Citation, build_grounded_answer


def test_build_assembles_cited_passage_with_registry_index(make_chunk):
    first = make_chunk(content="zero", ticker="AAPL", fiscal_year=2024)
    second = make_chunk(content="one", ticker="MSFT", fiscal_year=2023)
    retrieved = {first.id: first, second.id: second}  # insertion order: 0, 1

    reply = AgentReply(
        answer="Microsoft did X.",
        citations=[Citation(chunk_id=second.id, claim_text="X")],
    )
    grounded = build_grounded_answer(reply, retrieved)

    assert grounded.citations == reply.citations
    assert len(grounded.cited_passages) == 1
    passage = grounded.cited_passages[0]
    assert passage.chunk_id == second.id
    assert passage.passage_index == 1  # position in the retrieved set
    assert passage.ticker == "MSFT"
    assert passage.excerpt == "one"


def test_build_dedupes_repeated_citation_chunk(make_chunk):
    chunk = make_chunk()
    reply = AgentReply(
        answer="a",
        citations=[
            Citation(chunk_id=chunk.id, claim_text="x"),
            Citation(chunk_id=chunk.id, claim_text="y"),
        ],
    )
    grounded = build_grounded_answer(reply, {chunk.id: chunk})
    assert len(grounded.cited_passages) == 1


def test_refusal_has_no_cited_passages():
    reply = AgentReply(answer="No evidence.", refused=True, citations=[])
    grounded = build_grounded_answer(reply, {})
    assert grounded.refused is True
    assert grounded.cited_passages == []
