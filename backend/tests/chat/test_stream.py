import asyncio
import json
import uuid
from types import SimpleNamespace

from app.chat import stream
from app.chat.stream import finish_frame, stub_turn, text_chunk


def test_text_chunk_json_encodes_token():
    assert text_chunk('he said "hi"') == '0:"he said \\"hi\\""\n'


def test_text_chunk_escapes_newlines_into_one_line():
    line = text_chunk("multi\nline")
    # The protocol is newline-delimited: a newline inside the token must be
    # escaped by the JSON encoding, leaving exactly the trailing delimiter.
    assert line.startswith("0:")
    assert line.count("\n") == 1
    assert json.loads(line[2:]) == "multi\nline"


def test_finish_frame_shape():
    line = finish_frame()
    assert line.startswith("d:")
    assert line.endswith("\n")
    payload = json.loads(line[2:])
    assert payload["finishReason"] == "stop"
    assert payload["usage"] == {"promptTokens": 0, "completionTokens": 0}


def test_finish_frame_reports_usage():
    payload = json.loads(finish_frame(12, 34)[2:])
    assert payload["usage"] == {"promptTokens": 12, "completionTokens": 34}


def _drain(thread_id, svc):
    async def run():
        return [chunk async for chunk in stub_turn(thread_id, svc)]

    return asyncio.run(run())


def test_stub_turn_streams_text_then_finish_frame(monkeypatch):
    monkeypatch.setattr(stream.thread_db, "save_message", _noop_save([]))

    chunks = _drain(uuid.uuid4(), SimpleNamespace())

    assert chunks[-1].startswith("d:")
    assert all(c.startswith("0:") for c in chunks[:-1])

    reply = "".join(json.loads(c[2:]) for c in chunks[:-1])
    assert reply == "".join(stream._STUB_TOKENS)


def test_stub_turn_persists_only_the_assistant_reply(monkeypatch):
    # The route persists the user message before streaming; stub_turn must not
    # double-write it, only the assistant reply once the stream completes.
    saved: list[tuple[str, str]] = []
    monkeypatch.setattr(stream.thread_db, "save_message", _noop_save(saved))

    thread_id = uuid.uuid4()
    _drain(thread_id, SimpleNamespace())

    assert saved == [("assistant", "".join(stream._STUB_TOKENS))]


def _noop_save(sink: list):
    async def save_message(client, thread_id, role, content):
        sink.append((role, content))

    return save_message
