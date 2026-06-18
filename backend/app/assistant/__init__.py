"""The grounded-answer agent's typed contract.

The agent instance itself lives in ``app.assistant.agent`` — import it from there
(``from app.assistant.agent import agent``) so the submodule name isn't shadowed.
"""

from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import (
    AgentReply,
    Citation,
    GroundedAnswer,
    SourcePassage,
    build_grounded_answer,
)

__all__ = [
    "DocumentAgentDeps",
    "AgentReply",
    "Citation",
    "GroundedAnswer",
    "SourcePassage",
    "build_grounded_answer",
]
