"""Unit tests for Reciprocal Rank Fusion."""

import pytest

from app.retrieval.fusion import reciprocal_rank_fusion


def test_single_list_passes_through_in_order():
    fused = reciprocal_rank_fusion([["a", "b", "c"]], k=60)
    assert [item for item, _ in fused] == ["a", "b", "c"]
    # Scores decay with rank: 1/61 > 1/62 > 1/63.
    assert [score for _, score in fused] == [
        pytest.approx(1 / 61),
        pytest.approx(1 / 62),
        pytest.approx(1 / 63),
    ]


def test_item_in_both_lists_outranks_single_list_items():
    # "a" appears in both arms; everything else appears once.
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["d", "a"]], k=60)
    order = [item for item, _ in fused]
    assert order[0] == "a"
    # "a" = 1/61 + 1/62; "d" = 1/61; so a > d > b > c.
    assert order == ["a", "d", "b", "c"]


def test_k_controls_score_magnitude():
    fused = dict(reciprocal_rank_fusion([["x", "y"]], k=1))
    assert fused["x"] == pytest.approx(1 / 2)
    assert fused["y"] == pytest.approx(1 / 3)


def test_empty_input_yields_empty_ranking():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []


def test_ties_keep_first_appearance_order():
    # Symmetric lists give "a" and "b" identical scores; order must be stable.
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "a"]], k=60)
    items = [item for item, _ in fused]
    scores = [score for _, score in fused]
    assert items == ["a", "b"]
    assert scores[0] == pytest.approx(scores[1])
