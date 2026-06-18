"""Heading-anchored, token-bounded chunker for converted 10-K Markdown.

The strategy is documented in docs/architecture.md ("Chunking and embedding").
Summary: 10-K Markdown has a strong but shallow structure — `## PART` and
`### Item` headings, with no deeper headings and Item sizes spanning four orders
of magnitude. This splitter:

  1. strips running-header / page-footer noise (and records page numbers where
     the filing prints them),
  2. hard-splits on `## PART` / `### Item` headings — a chunk never crosses an
     Item boundary,
  3. packs the prose/table blocks inside each section to a token budget, with a
     one-paragraph overlap between adjacent prose chunks,
  4. keeps each Markdown table atomic — never split mid-row; an oversized table
     is split on row boundaries with its header (and caption) repeated.

The breadcrumb (e.g. "PART I > Item 1A. Risk Factors") is returned as each
chunk's ``section``; the ingest writer prepends it to the text it sends to the
embedder so section context rides along with the embedding.

Pure and dependency-free: no DB, no network, deterministic. Token counts are a
chars/4 estimate, which is conservative for the digit/punctuation-heavy
financial tables (it over-counts there, yielding smaller, safer chunks).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Budgets, in estimated tokens. Sized to the text-embedding-004 ~2,048-token
# input cap with a wide safety margin; target/overlap tuned for retrieval
# precision. See docs/architecture.md.
TARGET_TOKENS = 512
MAX_TOKENS = 800
OVERLAP_MAX_TOKENS = 200  # a prose block is only reused as overlap if it fits this
CAPTION_MAX_TOKENS = 40  # a short prose block right before a table is its caption

_PART_RE = re.compile(r"^##\s+(PART\s+[IVX]+)\b", re.IGNORECASE)
_ITEM_RE = re.compile(r"^###\s+(Item\s+\d+[A-C]?\b.*)$", re.IGNORECASE)
# In-document anchor links docling emits: [visible text](#i<hex>_<n>). Keep the
# visible text, drop the anchor target.
_ANCHOR_RE = re.compile(r"\[([^\]]*)\]\(#i[0-9a-f]+(?:_\d+)?\)")
# Page footer printed at the bottom of each page, e.g. "Apple Inc. | 2024 Form 10-K | 7".
_FOOTER_RE = re.compile(r"Form\s+10-K\s*\|\s*(\d+)\s*$", re.IGNORECASE)
# Markdown table separator row: only pipes, dashes, colons, spaces, with a dash.
_TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]*-[\s\-:|]*\|?\s*$")


@dataclass(frozen=True)
class Chunk:
    """A retrieval-ready passage. ``chunk_index`` is assigned by the writer."""

    content: str
    section: str | None
    page: int | None
    token_count: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


@dataclass
class _Line:
    text: str
    page: int | None


@dataclass
class _Section:
    breadcrumb: str | None
    lines: list[_Line]


@dataclass
class _Block:
    kind: str  # "prose" | "table"
    text: str
    page: int | None
    tokens: int
    header: str = ""  # table only: header rows to repeat when row-splitting
    caption: str = ""  # table only: caption to repeat when row-splitting


def _is_nav_line(text: str) -> bool:
    """A running-header "Table of Contents" navigation line (after anchors stripped)."""
    stripped = text.strip().strip("|").strip()
    return stripped.lower().startswith("table of contents")


def _clean_lines(markdown: str) -> list[_Line]:
    """Strip anchors, drop nav/footer noise, and tag each line with its page.

    Footers print at the bottom of a page, so a line's page is the number of the
    next footer at or after it. Filings without printed page numbers (most of the
    corpus except Apple) leave every page as ``None``, which is fine.
    """
    raw = [_ANCHOR_RE.sub(r"\1", line) for line in markdown.splitlines()]

    # Resolve each line's page from the next footer at or below it.
    next_page: list[int | None] = [None] * len(raw)
    upcoming: int | None = None
    for i in range(len(raw) - 1, -1, -1):
        m = _FOOTER_RE.search(raw[i])
        if m:
            upcoming = int(m.group(1))
        next_page[i] = upcoming

    out: list[_Line] = []
    for line, page in zip(raw, next_page):
        if _FOOTER_RE.search(line) or _is_nav_line(line):
            continue
        out.append(_Line(line, page))
    return out


def _normalize_heading(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _split_sections(lines: list[_Line]) -> list[_Section]:
    """Hard-split into sections at every `## PART` / `### Item` heading.

    The heading text becomes the section breadcrumb and is not emitted as body.
    """
    sections: list[_Section] = []
    part: str | None = None
    item: str | None = None
    current: list[_Line] = []

    def breadcrumb() -> str | None:
        return " > ".join(p for p in (part, item) if p) or None

    def flush() -> None:
        if any(line.text.strip() for line in current):
            sections.append(_Section(breadcrumb(), current.copy()))
        current.clear()

    for line in lines:
        part_m = _PART_RE.match(line.text)
        item_m = _ITEM_RE.match(line.text)
        if part_m:
            flush()
            part = _normalize_heading(part_m.group(1))
            item = None
        elif item_m:
            flush()
            item = _normalize_heading(item_m.group(1))
        else:
            current.append(line)
    flush()
    return sections


def _table_header(table_lines: list[str]) -> str:
    """The leading rows of a table to repeat in each split piece (through the separator)."""
    for i, line in enumerate(table_lines):
        if _TABLE_SEP_RE.match(line.strip()):
            return "\n".join(table_lines[: i + 1])
    return table_lines[0]  # no separator row; repeat the first row


def _parse_blocks(lines: list[_Line]) -> list[_Block]:
    """Group section lines into prose paragraphs and atomic tables."""
    blocks: list[_Block] = []
    i, n = 0, len(lines)
    while i < n:
        text = lines[i].text.strip()
        if not text:
            i += 1
            continue
        start = i
        if text.startswith("|"):
            while i < n and lines[i].text.strip().startswith("|"):
                i += 1
            table_lines = [lines[j].text.rstrip() for j in range(start, i)]
            body = "\n".join(table_lines)
            blocks.append(
                _Block(
                    "table",
                    body,
                    lines[start].page,
                    estimate_tokens(body),
                    header=_table_header(table_lines),
                )
            )
        else:
            while (
                i < n
                and lines[i].text.strip()
                and not lines[i].text.strip().startswith("|")
            ):
                i += 1
            body = "\n".join(lines[j].text.rstrip() for j in range(start, i)).strip()
            blocks.append(_Block("prose", body, lines[start].page, estimate_tokens(body)))
    return _merge_captions(blocks)


def _merge_captions(blocks: list[_Block]) -> list[_Block]:
    """Fold a short prose block immediately before a table into that table.

    The caption text stays in the chunk (it leads the table) and is remembered so
    it can be repeated when an oversized table is split on row boundaries.
    """
    merged: list[_Block] = []
    for block in blocks:
        if (
            block.kind == "table"
            and merged
            and merged[-1].kind == "prose"
            and merged[-1].tokens <= CAPTION_MAX_TOKENS
        ):
            caption = merged.pop()
            text = f"{caption.text}\n\n{block.text}"
            block = _Block(
                "table",
                text,
                caption.page,
                estimate_tokens(text),
                header=block.header,
                caption=caption.text,
            )
        merged.append(block)
    return merged


def _split_prose(text: str) -> list[str]:
    """Split an over-long paragraph on sentence boundaries, packed to the target."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    buf: list[str] = []
    size = 0
    for sentence in sentences:
        tokens = estimate_tokens(sentence)
        if buf and size + tokens > TARGET_TOKENS:
            pieces.append(" ".join(buf))
            buf, size = [], 0
        buf.append(sentence)
        size += tokens
    if buf:
        pieces.append(" ".join(buf))
    return pieces


def _split_table(block: _Block) -> list[str]:
    """Split an oversized table on row boundaries, repeating caption + header."""
    lines = block.text.splitlines()
    header_lines = block.header.splitlines()
    # Body rows are everything after the header rows.
    body_rows = lines[len(header_lines) + (1 if block.caption else 0) :]
    prefix = (f"{block.caption}\n" if block.caption else "") + block.header
    prefix_tokens = estimate_tokens(prefix)

    pieces: list[str] = []
    buf: list[str] = []
    size = prefix_tokens
    for row in body_rows:
        tokens = estimate_tokens(row)
        if buf and size + tokens > TARGET_TOKENS:
            pieces.append(prefix + "\n" + "\n".join(buf))
            buf, size = [], prefix_tokens
        buf.append(row)
        size += tokens
    if buf:
        pieces.append(prefix + "\n" + "\n".join(buf))
    return pieces


def _pack(blocks: list[_Block]) -> list[tuple[str, int | None]]:
    """Pack a section's blocks into (text, page) chunks near the token target.

    Greedy: accumulate blocks until adding the next would exceed MAX, or until we
    pass TARGET, then emit. The trailing prose block of a chunk seeds the next one
    (when it fits) so adjacent prose chunks overlap by a paragraph; the seed is
    only carried when it keeps the next chunk within MAX. Oversized blocks are
    split first and never carry overlap.
    """
    chunks: list[tuple[str, int | None]] = []
    buf: list[_Block] = []
    size = 0
    overlap: _Block | None = None

    def page_of(group: list[_Block]) -> int | None:
        for block in group:
            if block.page is not None:
                return block.page
        return None

    def emit() -> None:
        nonlocal buf, size, overlap
        if not buf:
            return
        chunks.append(("\n\n".join(b.text for b in buf), page_of(buf)))
        last = buf[-1]
        overlap = last if last.kind == "prose" and last.tokens <= OVERLAP_MAX_TOKENS else None
        buf, size = [], 0

    def seed(block: _Block) -> None:
        """Start a fresh chunk with the pending overlap if it leaves room for block."""
        nonlocal buf, size, overlap
        if not buf and overlap and overlap.tokens + block.tokens <= MAX_TOKENS:
            buf, size = [overlap], overlap.tokens
        overlap = None

    for block in blocks:
        if block.tokens > MAX_TOKENS:
            emit()
            overlap = None
            split = _split_table(block) if block.kind == "table" else _split_prose(block.text)
            for piece in split:
                chunks.append((piece, block.page))
            continue
        seed(block)
        if buf and size + block.tokens > MAX_TOKENS:
            emit()
            seed(block)
        buf.append(block)
        size += block.tokens
        if size >= TARGET_TOKENS:
            emit()
    emit()
    return chunks


def chunk_markdown(markdown: str) -> list[Chunk]:
    """Split converted 10-K Markdown into retrieval-ready chunks."""
    chunks: list[Chunk] = []
    for section in _split_sections(_clean_lines(markdown)):
        for text, page in _pack(_parse_blocks(section.lines)):
            content = text.strip()
            if not content:
                continue
            chunks.append(Chunk(content, section.breadcrumb, page, estimate_tokens(content)))
    return chunks


if __name__ == "__main__":
    # Quick stats over the local corpus: uv run python ingest/chunk.py
    from pathlib import Path

    markdown_dir = Path(__file__).resolve().parents[2] / "data" / "markdown"
    total = 0
    over_cap = 0
    for path in sorted(markdown_dir.rglob("*.md")):
        cs = chunk_markdown(path.read_text(encoding="utf-8"))
        total += len(cs)
        toks = [c.token_count for c in cs]
        over = sum(1 for t in toks if t > 2048)
        over_cap += over
        print(
            f"{path.parent.name}/{path.name:<55} chunks={len(cs):4d} "
            f"avg={sum(toks) // len(toks):4d} max={max(toks):5d} over2048={over}"
        )
    print(f"\nTotal chunks: {total}   chunks over embed cap (2048): {over_cap}")
