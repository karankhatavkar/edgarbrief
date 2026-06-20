"""Orchestration tests for one chat turn — streaming framing + persistence.

The model is scripted with ``TestModel``, ``retrieve`` and the DB session are
stubbed, and persistence is monkeypatched, so the whole turn runs with no
network or database.
"""

import asyncio
import uuid
from types import SimpleNamespace

from pydantic_ai.models.test import TestModel
from structlog.testing import capture_logs

import app.assistant.agent as agent_mod
from app.assistant.agent import agent
from app.chat import orchestrator
from app.chat.orchestrator import run_chat_turn


class _FakeSessionCtx:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


def _stub_turn_io(monkeypatch, chunk):
    async def fake_retrieve(session, query, **kwargs):
        return [SimpleNamespace(chunk=chunk, neighbors=[], score=1.0)]

    async def fake_record_usage(user_id, tokens, requests):
        return None

    monkeypatch.setattr(agent_mod, "retrieve", fake_retrieve)
    monkeypatch.setattr(orchestrator, "async_session", lambda: _FakeSessionCtx())
    monkeypatch.setattr(orchestrator, "record_usage", fake_record_usage)


def _drain(gen):
    async def run():
        return [line async for line in gen]

    return asyncio.run(run())


def _model(cited_chunk_id: uuid.UUID) -> TestModel:
    return TestModel(
        call_tools=["search_filings"],
        custom_output_args={
            "answer": "Apple did X.",
            "refused": False,
            "citations": [{"chunk_id": str(cited_chunk_id), "claim_text": "X"}],
        },
    )


def test_run_chat_turn_streams_and_persists(monkeypatch, make_chunk):
    chunk = make_chunk()
    _stub_turn_io(monkeypatch, chunk)

    saved: dict = {}

    async def fake_save(client, thread_id, answer, citation_rows):
        saved["answer"] = answer
        saved["rows"] = citation_rows
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(orchestrator.thread_db, "save_assistant_message", fake_save)

    with agent.override(model=_model(chunk.id)):
        lines = _drain(run_chat_turn(SimpleNamespace(), uuid.uuid4(), "q", uuid.uuid4()))

    assert any(line.startswith("0:") for line in lines)  # text deltas
    assert any(line.startswith("8:") for line in lines)  # citations part
    assert lines[-1].startswith("d:")  # finish
    assert saved["answer"] == "Apple did X."
    assert saved["rows"] == [
        {"chunk_id": str(chunk.id), "claim_text": "X", "passage_index": 0}
    ]


def test_run_chat_turn_titles_first_turn(monkeypatch, make_chunk):
    chunk = make_chunk()
    _stub_turn_io(monkeypatch, chunk)

    async def fake_save(*args, **kwargs):
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_count(client, thread_id):
        return 2  # one user + one assistant message => first turn

    titled: dict = {}

    async def fake_update(client, thread_id, title):
        titled["title"] = title

    async def fake_generate(question, answer):
        return "Apple Revenue Title"

    monkeypatch.setattr(orchestrator.thread_db, "save_assistant_message", fake_save)
    monkeypatch.setattr(orchestrator.thread_db, "count_messages", fake_count)
    monkeypatch.setattr(orchestrator.thread_db, "update_thread_title", fake_update)
    monkeypatch.setattr(orchestrator, "generate_thread_title", fake_generate)

    with agent.override(model=_model(chunk.id)):
        _drain(run_chat_turn(SimpleNamespace(), uuid.uuid4(), "q", uuid.uuid4()))

    assert titled["title"] == "Apple Revenue Title"


def test_run_chat_turn_skips_title_on_later_turns(monkeypatch, make_chunk):
    chunk = make_chunk()
    _stub_turn_io(monkeypatch, chunk)

    async def fake_save(*args, **kwargs):
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_count(client, thread_id):
        return 4  # not the first turn

    called = {"generate": False, "update": False}

    async def fake_generate(question, answer):
        called["generate"] = True
        return "Should Not Run"

    async def fake_update(*args, **kwargs):
        called["update"] = True

    monkeypatch.setattr(orchestrator.thread_db, "save_assistant_message", fake_save)
    monkeypatch.setattr(orchestrator.thread_db, "count_messages", fake_count)
    monkeypatch.setattr(orchestrator.thread_db, "update_thread_title", fake_update)
    monkeypatch.setattr(orchestrator, "generate_thread_title", fake_generate)

    with agent.override(model=_model(chunk.id)):
        _drain(run_chat_turn(SimpleNamespace(), uuid.uuid4(), "q", uuid.uuid4()))

    assert called == {"generate": False, "update": False}


def test_run_chat_turn_title_failure_is_swallowed(monkeypatch, make_chunk):
    chunk = make_chunk()
    _stub_turn_io(monkeypatch, chunk)

    async def fake_save(*args, **kwargs):
        return SimpleNamespace(id=uuid.uuid4())

    async def fake_count(client, thread_id):
        return 2

    async def boom(question, answer):
        raise RuntimeError("gemini exploded")

    monkeypatch.setattr(orchestrator.thread_db, "save_assistant_message", fake_save)
    monkeypatch.setattr(orchestrator.thread_db, "count_messages", fake_count)
    monkeypatch.setattr(orchestrator, "generate_thread_title", boom)

    with capture_logs() as logs:
        with agent.override(model=_model(chunk.id)):
            lines = _drain(run_chat_turn(SimpleNamespace(), uuid.uuid4(), "q", uuid.uuid4()))

    # The turn still completes cleanly; the title failure is logged, not raised.
    assert lines[-1].startswith("d:")
    assert any(entry["event"] == "turn.title_failed" for entry in logs)


def test_run_chat_turn_grounding_failure_emits_error_and_skips_persist(
    monkeypatch, make_chunk
):
    chunk = make_chunk()
    _stub_turn_io(monkeypatch, chunk)

    called = {"save": False}

    async def fake_save(*args, **kwargs):
        called["save"] = True
        return SimpleNamespace(id=uuid.uuid4())

    monkeypatch.setattr(orchestrator.thread_db, "save_assistant_message", fake_save)

    # Output cites a chunk that was never retrieved -> turn fails closed.
    with agent.override(model=_model(uuid.uuid4())):
        lines = _drain(run_chat_turn(SimpleNamespace(), uuid.uuid4(), "q", uuid.uuid4()))

    assert any(line.startswith("3:") for line in lines)  # error part
    assert lines[-1].startswith("d:")
    assert called["save"] is False


def test_run_chat_turn_unexpected_failure_degrades_and_logs(monkeypatch):
    """A retrieval/LLM/DB error mid-run must not leak a 500 or drop silently."""
    called = {"save": False}

    async def boom(*args, **kwargs):
        raise RuntimeError("gemini exploded")

    async def fake_save(*args, **kwargs):
        called["save"] = True

    monkeypatch.setattr(orchestrator, "agent", SimpleNamespace(run=boom))
    monkeypatch.setattr(orchestrator.thread_db, "save_assistant_message", fake_save)

    with capture_logs() as logs:
        lines = _drain(run_chat_turn(SimpleNamespace(), uuid.uuid4(), "q", uuid.uuid4()))

    assert any(line.startswith("3:") for line in lines)  # graceful error part
    assert lines[-1].startswith("d:")  # finish frame, not a raised exception
    assert called["save"] is False
    assert any(entry["event"] == "turn.failed" for entry in logs)
