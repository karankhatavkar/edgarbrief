"""Unit tests for thread-title generation — sanitizing and the LLM call.

The Gemini client is mocked at the boundary, so these hit no network.
"""

import asyncio
from types import SimpleNamespace

from app.chat import titling
from app.chat.titling import _answer_excerpt, _clean_title, generate_thread_title


def test_answer_excerpt_takes_first_two_nonempty_lines():
    answer = "## Heading\n\nApple grew revenue.\n\nMore detail here.\nAnd even more."
    excerpt = _answer_excerpt(answer)
    assert excerpt == "## Heading Apple grew revenue."


def test_answer_excerpt_is_char_capped():
    answer = "x" * 1000
    assert len(_answer_excerpt(answer)) == titling._ANSWER_MAX_CHARS


def test_clean_title_strips_quotes_punctuation_and_whitespace():
    assert _clean_title('  "Apple FY23 Revenue Growth."  \n') == "Apple FY23 Revenue Growth"


def test_clean_title_collapses_internal_whitespace():
    assert _clean_title("Tesla   Risk\nFactors") == "Tesla Risk Factors"


def test_clean_title_rejects_empty():
    assert _clean_title('  "" ') is None


def test_clean_title_enforces_max_length():
    out = _clean_title("word " * 40)
    assert out is not None
    assert len(out) <= titling._TITLE_MAX_CHARS


def _mock_client(monkeypatch, text):
    async def fake_generate(*, model, contents, config):
        return SimpleNamespace(text=text)

    client = SimpleNamespace(aio=SimpleNamespace(models=SimpleNamespace(generate_content=fake_generate)))
    monkeypatch.setattr(titling, "_get_client", lambda: client)


def test_generate_thread_title_returns_cleaned_title(monkeypatch):
    _mock_client(monkeypatch, '"Apple FY23 Revenue Growth"')
    title = asyncio.run(generate_thread_title("How did Apple do?", "Apple grew."))
    assert title == "Apple FY23 Revenue Growth"


def test_generate_thread_title_none_when_model_returns_blank(monkeypatch):
    _mock_client(monkeypatch, "")
    assert asyncio.run(generate_thread_title("q", "a")) is None
