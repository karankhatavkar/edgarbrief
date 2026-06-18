"""AI SDK data-stream framing for one chat turn.

Emits the Vercel AI SDK data-stream protocol so `useChat` works with no frontend
configuration:

  0:"token"\n        — text delta (JSON-encoded string)
  8:[{...}]\n        — source/citation metadata parts
  3:"message"\n      — error part (grounding or LLM failure)
  d:{...}\n          — finish metadata

The frame builders are isolated and unit-tested because this is the wire
contract with the frontend: a typo here silently breaks chat.
"""

import json
import re
from collections.abc import Iterable

# Header that tells the AI SDK client to parse the data-stream protocol below.
DATA_STREAM_HEADERS = {"x-vercel-ai-data-stream": "v1"}


def text_chunk(text: str) -> str:
    """Format one text delta as an AI SDK data-stream line."""
    return f"0:{json.dumps(text)}\n"


def citations_part(passages: list[dict]) -> str:
    """Format cited source passages as an AI SDK data part."""
    return f"8:{json.dumps(passages)}\n"


def error_part(message: str) -> str:
    """Format an error line — used when a turn fails closed."""
    return f"3:{json.dumps(message)}\n"


def finish_frame(prompt_tokens: int = 0, completion_tokens: int = 0) -> str:
    """Format the terminating finish line of an AI SDK data-stream."""
    payload = {
        "finishReason": "stop",
        "usage": {
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
        },
    }
    return f"d:{json.dumps(payload)}\n"


def answer_deltas(text: str) -> Iterable[str]:
    """Split a validated answer into tokens for progressive streaming.

    Whitespace is preserved with each token so the joined deltas reproduce the
    original text exactly.
    """
    return re.findall(r"\S+\s*", text)
