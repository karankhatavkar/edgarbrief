"""Unit tests for the AI SDK data-stream frame builders."""

import json

from app.chat import streaming


def test_text_chunk_json_encodes_token():
    assert streaming.text_chunk('he said "hi"') == '0:"he said \\"hi\\""\n'


def test_citations_part_shape():
    line = streaming.citations_part([{"chunk_id": "abc", "page": 12}])
    assert line.startswith("8:")
    assert line.endswith("\n")
    assert json.loads(line[2:]) == [{"chunk_id": "abc", "page": 12}]


def test_error_part_shape():
    line = streaming.error_part("grounding failed")
    assert line.startswith("3:")
    assert json.loads(line[2:]) == "grounding failed"


def test_finish_frame_reports_usage():
    payload = json.loads(streaming.finish_frame(3, 4)[2:])
    assert payload["finishReason"] == "stop"
    assert payload["usage"] == {"promptTokens": 3, "completionTokens": 4}


def test_answer_deltas_reconstruct_original_text():
    text = "Apple grew revenue.  Services rose too."
    assert "".join(streaming.answer_deltas(text)) == text


def test_answer_deltas_on_empty_text():
    assert list(streaming.answer_deltas("")) == []
