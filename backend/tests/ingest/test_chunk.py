"""Unit tests for the heading-anchored Markdown chunker."""

from pathlib import Path

import pytest

from ingest.chunk import (
    MAX_TOKENS,
    OVERLAP_MAX_TOKENS,
    Chunk,
    chunk_markdown,
    estimate_tokens,
)

# A paragraph whose token estimate is known and small, for composing fixtures.
PARA = "word " * 40  # ~200 chars -> ~50 tokens


def _para(n: int, label: str) -> str:
    """A distinct paragraph of roughly `n` tokens, tagged with `label`."""
    return (f"{label} " + "filler " * (n * 4 // 7)).strip()


def test_estimate_tokens_is_chars_over_four():
    assert estimate_tokens("a" * 400) == 100
    assert estimate_tokens("") == 1  # floored to at least 1


def test_returns_chunk_objects_with_metadata():
    md = "## PART I\n\n### Item 1. Business\n\nSome prose about the business."
    chunks = chunk_markdown(md)
    assert chunks and all(isinstance(c, Chunk) for c in chunks)
    assert chunks[0].section == "PART I > Item 1. Business"
    assert chunks[0].token_count == estimate_tokens(chunks[0].content)


def test_breadcrumb_combines_part_and_item():
    md = "## PART II\n\n### Item 7A. Market Risk\n\nDisclosure text here."
    assert chunk_markdown(md)[0].section == "PART II > Item 7A. Market Risk"


def test_heading_whitespace_is_normalized():
    md = "### Item 1A.    Risk    Factors\n\nbody"
    assert chunk_markdown(md)[0].section == "Item 1A. Risk Factors"


def test_chunks_never_cross_item_boundaries():
    md = (
        "### Item 1. Business\n\n" + _para(300, "alpha") + "\n\n"
        "### Item 2. Properties\n\n" + _para(300, "bravo")
    )
    chunks = chunk_markdown(md)
    # No chunk may contain text from two different items.
    for c in chunks:
        assert not ("alpha" in c.content and "bravo" in c.content)
    assert {c.section for c in chunks} == {"Item 1. Business", "Item 2. Properties"}


def test_strips_footers_anchors_and_nav_and_captures_page():
    md = (
        "### Item 1. Business\n\n"
        "Real content one.\n\n"
        "[Table of Contents](#iabc123_7)\n\n"
        "See [Note 1](#idef456_9) for details.\n\n"
        "Real content two.\n\n"
        "Acme Inc. | 2024 Form 10-K | 7\n"
    )
    chunks = chunk_markdown(md)
    joined = "\n".join(c.content for c in chunks)
    assert "#i" not in joined
    assert "Table of Contents" not in joined
    assert "Form 10-K | 7" not in joined
    assert "See Note 1 for details." in joined  # anchor text kept, target dropped
    # Content above the footer is on page 7.
    assert chunks[0].page == 7


def test_no_page_number_leaves_page_none():
    md = "### Item 1. Business\n\nNo footer here, so no page."
    assert chunk_markdown(md)[0].page is None


def test_small_table_is_kept_atomic():
    table = "\n".join(["| a | b |", "| - | - |"] + [f"| {i} | {i * 2} |" for i in range(5)])
    md = f"### Item 8. Financials\n\nIntro paragraph.\n\n{table}"
    chunks = chunk_markdown(md)
    table_chunks = [c for c in chunks if "| 3 | 6 |" in c.content]
    assert len(table_chunks) == 1
    # Every row of the table survives in that one chunk.
    for i in range(5):
        assert f"| {i} | {i * 2} |" in table_chunks[0].content


def test_oversized_table_splits_on_rows_and_repeats_header():
    rows = [f"| metric {i} | {i} | {i + 1} |" for i in range(400)]
    table = "\n".join(["| name | y1 | y2 |", "| - | - | - |"] + rows)
    md = f"### Item 8. Financials\n\n{table}"
    chunks = chunk_markdown(md)
    table_chunks = [c for c in chunks if c.content.lstrip().startswith("| name | y1 | y2 |")]
    assert len(table_chunks) > 1  # had to split
    for c in table_chunks:
        assert c.content.splitlines()[0] == "| name | y1 | y2 |"  # header repeated
        assert c.token_count <= MAX_TOKENS
    # No data row is lost or duplicated across the pieces.
    seen = [line for c in table_chunks for line in c.content.splitlines() if line.startswith("| metric")]
    assert len(seen) == len(set(seen)) == 400


def test_table_caption_is_repeated_when_split():
    rows = [f"| metric {i} | {i} |" for i in range(400)]
    table = "\n".join(["| name | y1 |", "| - | - |"] + rows)
    md = f"### Item 8. Financials\n\nNET SALES BY SEGMENT\n\n{table}"
    chunks = chunk_markdown(md)
    pieces = [c for c in chunks if "| name | y1 |" in c.content]
    assert len(pieces) > 1
    assert all("NET SALES BY SEGMENT" in c.content for c in pieces)


def test_oversized_paragraph_splits_on_sentences():
    sentence = "This is a sentence about revenue and risk. "
    big = sentence * 200  # well over MAX_TOKENS, many sentence boundaries
    md = f"### Item 1A. Risk Factors\n\n{big}"
    chunks = chunk_markdown(md)
    assert len(chunks) > 1
    assert all(c.token_count <= MAX_TOKENS for c in chunks)


def test_adjacent_prose_chunks_overlap_by_a_paragraph():
    paras = [_para(200, f"p{i}") for i in range(6)]
    md = "### Item 1A. Risk Factors\n\n" + "\n\n".join(paras)
    chunks = chunk_markdown(md)
    assert len(chunks) > 1
    # The last paragraph of each chunk should reappear opening the next one.
    for first, second in zip(chunks, chunks[1:]):
        last_label = next(lbl for lbl in (f"p{i}" for i in range(6)) if lbl in first.content.split("\n\n")[-1])
        assert last_label in second.content.split("\n\n")[0]


def test_no_empty_chunks_and_sizes_bounded():
    md = "### Item 1A. Risk Factors\n\n" + "\n\n".join(_para(120, f"p{i}") for i in range(20))
    for c in chunk_markdown(md):
        assert c.content.strip()
        # Bounded by MAX plus a possible overlap paragraph; far under the 2048 cap.
        assert c.token_count <= MAX_TOKENS + OVERLAP_MAX_TOKENS


def test_empty_or_headingless_document():
    assert chunk_markdown("") == []
    assert chunk_markdown("\n\n   \n") == []
    # Preamble before any heading still produces a chunk with no section.
    chunks = chunk_markdown("Loose intro text before any heading.")
    assert len(chunks) == 1 and chunks[0].section is None


# --- Corpus invariant (skipped when the gitignored data is absent) ----------

_CORPUS = Path(__file__).resolve().parents[2].parent / "data" / "markdown"


@pytest.mark.skipif(not _CORPUS.exists(), reason="local markdown corpus not present")
def test_corpus_chunks_stay_under_embed_cap():
    files = list(_CORPUS.rglob("*.md"))
    assert files, "corpus dir exists but has no markdown"
    for path in files:
        chunks = chunk_markdown(path.read_text(encoding="utf-8"))
        assert chunks, f"no chunks for {path.name}"
        for c in chunks:
            assert c.content.strip()
            assert c.token_count <= 2048, f"{path.name}: chunk over embed cap"
            # Breadcrumb preserves the issuer's heading casing (e.g. AAPL "PART I",
            # NVDA "Part I"), so compare case-insensitively.
            assert c.section is None or c.section.lower().startswith(("part", "item"))
