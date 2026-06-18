"""Unit tests for grounding enforcement."""

import uuid

import pytest

from app.assistant.outputs import AgentReply, Citation
from app.grounding.validator import GroundingError, validate_grounding


def _retrieved(*chunks):
    return {chunk.id: chunk for chunk in chunks}


def test_citation_to_retrieved_chunk_passes(make_chunk):
    chunk = make_chunk()
    reply = AgentReply(
        answer="Apple grew.", citations=[Citation(chunk_id=chunk.id, claim_text="grew")]
    )
    validate_grounding(reply, _retrieved(chunk))  # no raise


def test_non_refusal_without_citations_raises():
    reply = AgentReply(answer="Apple grew.", refused=False, citations=[])
    with pytest.raises(GroundingError):
        validate_grounding(reply, {})


def test_refusal_without_citations_is_allowed():
    reply = AgentReply(answer="Not enough evidence.", refused=True, citations=[])
    validate_grounding(reply, {})  # no raise


def test_citation_to_unretrieved_chunk_raises(make_chunk):
    chunk = make_chunk()
    reply = AgentReply(
        answer="Apple grew.",
        citations=[Citation(chunk_id=uuid.uuid4(), claim_text="grew")],
    )
    with pytest.raises(GroundingError):
        validate_grounding(reply, _retrieved(chunk))
