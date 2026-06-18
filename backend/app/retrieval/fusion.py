"""Reciprocal Rank Fusion — combine ranked lists from independent retrievers.

RRF scores each item by ``sum(1 / (k + rank))`` across the lists it appears in,
so an item ranked decently by *both* the vector and full-text arms beats one
ranked highly by a single arm. ``k`` damps the weight of top ranks (the standard
default is 60). Pure and DB-free, so it's trivially unit-testable on plain ids.
"""

from collections.abc import Hashable, Sequence

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion[K: Hashable](
    rankings: Sequence[Sequence[K]], k: int = DEFAULT_RRF_K
) -> list[tuple[K, float]]:
    """Fuse ranked lists into one ranking of ``(item, score)``, best first.

    Ties keep first-appearance order: ``dict`` preserves insertion order and
    Python's sort is stable, so the result is deterministic.
    """
    scores: dict[K, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda item_score: item_score[1], reverse=True)
