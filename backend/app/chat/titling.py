"""Generate a short, human-readable title for a chat thread.

A one-shot LLM call summarizing the thread's opening exchange into a few words,
run once after the first assistant turn. It reuses the chat model and the same
lazy async ``genai.Client`` pattern as ``app/retrieval/embedding.py``; titling
is best-effort, so callers treat a ``None`` return as "keep the existing title".
"""

from google import genai
from google.genai import types

from app.config import settings

_client: genai.Client | None = None

# Only the opening of the answer is needed for context; full markdown answers are
# long and the extra tokens don't improve a 3-6 word title.
_ANSWER_LINES = 2
_ANSWER_MAX_CHARS = 300
_TITLE_MAX_CHARS = 60

_PROMPT = """\
Write a concise title for this chat about SEC filings, summarizing what the user \
is asking about. Use Title Case, 3 to 6 words. No quotes, no trailing \
punctuation, no markdown.

Question: {question}

Answer: {answer}

Title:"""


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.gemini_api_key)
    return _client


def _answer_excerpt(answer: str) -> str:
    """First couple of non-empty lines of the answer, char-capped."""
    lines = [line.strip() for line in answer.splitlines() if line.strip()]
    excerpt = " ".join(lines[:_ANSWER_LINES])
    return excerpt[:_ANSWER_MAX_CHARS]


def _clean_title(raw: str) -> str | None:
    """Normalize model output to a single tidy line, or None if unusable."""
    title = " ".join(raw.split()).strip().strip("\"'").rstrip(".!?,;:")
    if not title:
        return None
    return title[:_TITLE_MAX_CHARS].strip()


async def generate_thread_title(question: str, answer: str) -> str | None:
    """Return a short title for the opening exchange, or None on failure."""
    prompt = _PROMPT.format(question=question, answer=_answer_excerpt(answer))
    # .aio keeps the call off the event loop's blocking path; max_output_tokens
    # is small because the title is only a few words.
    response = await _get_client().aio.models.generate_content(
        model=settings.gemini_chat_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3,
            max_output_tokens=24,
        ),
    )
    if not response.text:
        return None
    return _clean_title(response.text)
