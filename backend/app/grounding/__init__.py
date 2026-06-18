"""Grounding enforcement: every citation must map to a retrieved passage."""

from app.grounding.validator import GroundingError, validate_grounding

__all__ = ["GroundingError", "validate_grounding"]
