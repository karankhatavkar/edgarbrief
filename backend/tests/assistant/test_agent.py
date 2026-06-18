"""Grounding-enforcement tests for the agent, driven by a scripted model.

The LLM is replaced with ``TestModel`` (which calls ``search_filings`` then
returns our chosen output) and ``retrieve`` is stubbed, so these run with no
network or database. The point is the contract: an answer citing a chunk that
was never retrieved must fail closed.
"""

import uuid
from types import SimpleNamespace

import pytest
from pydantic_ai import UnexpectedModelBehavior
from pydantic_ai.models.test import TestModel

import app.assistant.agent as agent_mod
from app.assistant.agent import agent
from app.assistant.deps import DocumentAgentDeps


def _stub_retrieve(monkeypatch, chunk):
    async def fake_retrieve(session, query, **kwargs):
        return [SimpleNamespace(chunk=chunk, neighbors=[], score=1.0)]

    monkeypatch.setattr(agent_mod, "retrieve", fake_retrieve)


def _scripted_model(cited_chunk_id: uuid.UUID) -> TestModel:
    return TestModel(
        call_tools=["search_filings"],
        custom_output_args={
            "answer": "Apple disclosed something.",
            "refused": False,
            "citations": [{"chunk_id": str(cited_chunk_id), "claim_text": "disclosed"}],
        },
    )


def test_agent_accepts_grounded_citation(monkeypatch, make_chunk):
    chunk = make_chunk()
    _stub_retrieve(monkeypatch, chunk)
    deps = DocumentAgentDeps(session=None)

    with agent.override(model=_scripted_model(chunk.id)):
        result = agent.run_sync("How did Apple do?", deps=deps)

    assert result.output.citations[0].chunk_id == chunk.id
    assert chunk.id in deps.retrieved  # the tool registered what it showed


def test_agent_rejects_ungrounded_citation(monkeypatch, make_chunk):
    chunk = make_chunk()
    _stub_retrieve(monkeypatch, chunk)
    deps = DocumentAgentDeps(session=None)

    # Cite a chunk that was never retrieved this turn -> fail closed.
    with agent.override(model=_scripted_model(uuid.uuid4())):
        with pytest.raises(UnexpectedModelBehavior):
            agent.run_sync("How did Apple do?", deps=deps)
