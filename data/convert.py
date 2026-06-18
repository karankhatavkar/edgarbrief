# /// script
# requires-python = ">=3.12"
# dependencies = ["docling"]
# ///
from __future__ import annotations

import re
from io import BytesIO
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from docling.document_converter import DocumentConverter
from docling_core.types.io import DocumentStream

DOWNLOADS_DIR = Path(__file__).resolve().parent / "downloads"
MARKDOWN_DIR = Path(__file__).resolve().parent / "markdown"

SKIP_PATTERNS = {"manifest.json"}

# ---------------------------------------------------------------------------
# Stage 1: EDGAR HTML Cleaner
# ---------------------------------------------------------------------------

_PART_RE = re.compile(r"^(PART\s+(?:I{1,3}V?|IV))\s*$", re.IGNORECASE)
# \s*\S handles both "Item 1.Business" (AMZN) and "Item 1.    Business" (AAPL)
_ITEM_RE = re.compile(r"^(Item\s+\d+[A-C]?\.?)\s*\S", re.IGNORECASE)


def _normalize_table(table: Tag) -> None:
    """Remove phantom column duplication from EDGAR iXBRL financial tables.

    EDGAR encodes XBRL data with colspan="2" or colspan="3" on most cells for
    tag alignment. Docling expands each colspan literally, repeating the cell
    text N times. Value-equality detection fails when rows mix currency-prefixed
    cells (e.g. "$ | 167,045") with bare-value cells (e.g. colspan=2 "101,328")
    in the same column: the mixed left-neighbours prevent any column from being
    classified as phantom.

    Fix: strip all colspan attributes so every cell occupies exactly one column,
    then prune columns that are empty in every row of the table.
    """
    rows = table.find_all("tr")
    if not rows:
        return

    # Strip every colspan — each cell becomes a single column.
    for tr in rows:
        for cell in tr.find_all(["td", "th"]):
            cell.attrs.pop("colspan", None)

    # Build the single-column grid and find all-empty columns.
    grid = [
        [c.get_text(strip=True) for c in tr.find_all(["td", "th"])]
        for tr in rows
    ]
    max_cols = max((len(r) for r in grid), default=0)
    if not max_cols:
        return

    empty_cols = {
        col for col in range(max_cols)
        if not any(col < len(row) and row[col] for row in grid)
    }
    if not empty_cols:
        return

    for tr in rows:
        for col, cell in enumerate(list(tr.find_all(["td", "th"]))):
            if col in empty_cols:
                cell.decompose()


def _is_empty_table(table: Tag) -> bool:
    return not any(c.get_text(strip=True) for c in table.find_all(["td", "th"]))


def _inject_headings(soup: BeautifulSoup) -> None:
    """Promote plain-text Part/Item labels to <h2>/<h3> tags.

    EDGAR filings use unstyled <div> and <p> elements for section labels.
    Replacing them with semantic heading tags causes docling to emit proper
    ## / ### Markdown headings, which are essential for heading-based chunk
    splitting and section-level metadata in the ingestion pipeline.

    Each Part and Item label is only promoted once — duplicate occurrences
    (e.g. in a table of contents that was not inside a <table>) are skipped.
    """
    seen_parts: set[str] = set()
    seen_items: set[str] = set()

    for tag in soup.find_all(["p", "div"]):
        if tag.find_parent("table"):
            continue
        # Normalise non-breaking spaces before matching.
        text = tag.get_text(strip=True).replace("\xa0", " ").strip()

        if _PART_RE.match(text):
            key = text.upper()
            if key not in seen_parts:
                tag.name = "h2"
                seen_parts.add(key)

        elif _ITEM_RE.match(text):
            m = _ITEM_RE.match(text)
            key = m.group(1).upper()  # type: ignore[union-attr]
            if key not in seen_items:
                tag.name = "h3"
                seen_items.add(key)


def clean_edgar_html(raw_bytes: bytes) -> bytes:
    """Apply EDGAR-specific pre-processing before passing HTML to docling.

    Three transforms, in order:
      1. Strip the hidden XBRL metadata block (display:none div).
      2. Normalize table colspans — remove phantom duplicate columns.
      3. Inject semantic <h2>/<h3> heading tags for Part/Item labels.
    """
    soup = BeautifulSoup(raw_bytes, "html.parser")

    # 1. Remove hidden XBRL block (~88–300 KB of machine-readable metadata).
    for tag in soup.find_all(
        True, style=lambda s: s and "display:none" in s.replace(" ", "")
    ):
        tag.decompose()

    # 2. Normalize table colspans; drop tables that are entirely empty.
    for table in soup.find_all("table"):
        _normalize_table(table)
        if _is_empty_table(table):
            table.decompose()

    # 3. Inject semantic heading tags for section navigation.
    _inject_headings(soup)

    return soup.encode("utf-8")


# ---------------------------------------------------------------------------
# Stage 2: docling conversion
# ---------------------------------------------------------------------------

def convert_all() -> None:
    converter = DocumentConverter()

    htm_files = sorted(
        f
        for f in DOWNLOADS_DIR.rglob("*")
        if f.is_file() and f.name not in SKIP_PATTERNS
    )

    print(f"Found {len(htm_files)} file(s) to convert.")

    for src in htm_files:
        rel = src.relative_to(DOWNLOADS_DIR)
        dest = MARKDOWN_DIR / rel.with_suffix(".md")

        if dest.exists():
            print(f"  SKIP (exists): {rel}")
            continue

        dest.parent.mkdir(parents=True, exist_ok=True)
        print(f"  Converting: {rel} ...", end="", flush=True)

        cleaned = clean_edgar_html(src.read_bytes())
        stream = DocumentStream(name=src.name, stream=BytesIO(cleaned))

        result = converter.convert(stream, raises_on_error=False)
        if result.status.value not in ("success", "partial_success"):
            print(f" FAILED ({result.status})")
            continue

        dest.write_text(
            result.document.export_to_markdown(compact_tables=True),
            encoding="utf-8",
        )
        print(f" done ({dest.stat().st_size // 1024} KB)")

    print(f"\nMarkdown files saved to: {MARKDOWN_DIR}")


if __name__ == "__main__":
    convert_all()
