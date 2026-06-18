# Data

Local data artifacts for development live here. All downloaded payloads are gitignored; the scripts and notes stay in git.

```text
data/
├── download.py     # Fetches raw HTM filings from SEC EDGAR
├── convert.py      # Converts HTM → Markdown (EDGAR-aware, two-stage)
├── downloads/      # Raw source files from EDGAR, grouped by year (gitignored)
└── markdown/       # Converted Markdown files, mirroring downloads/ layout (gitignored)
```

---

## Fetching the corpus

```bash
uv run data/download.py
```

Downloads the latest five 10-K filings for AAPL, MSFT, NVDA, AMZN, and GOOGL into year folders under `data/downloads/` and writes a `manifest.json`. Edit `USER_AGENT` at the top of the script before running.

---

## Converting HTM → Markdown

```bash
uv run data/convert.py
```

Converts every `.htm` file under `data/downloads/` to `.md` under `data/markdown/`, preserving the year subfolder layout. Skips files that already have a corresponding `.md` output.

### Why a custom pipeline?

SEC EDGAR 10-K filings use Inline XBRL (iXBRL) format. Every `<td>` in a financial table carries a `colspan` attribute — typically `colspan="3"` — for structured data alignment. A vanilla HTML-to-Markdown converter expands each spanned cell into N identical copies, so a single "Net sales:" label becomes three columns:

```
| Net sales: | Net sales: | Net sales: |   # bad — vanilla docling default
| Net sales: |                              # good — after pre-processing
```

With the default docling pipeline, 83–96% of all financial table rows are triplicated across AAPL, AMZN, GOOGL, and NVDA filings. MSFT uses a different layout and was less affected (4%), but still had no heading hierarchy.

### Two-stage pipeline

```
raw .htm (iXBRL)  →  [Stage 1: EDGAR HTML Cleaner]  →  clean .htm  →  [Stage 2: docling]  →  .md
```

**Stage 1 — EDGAR HTML Cleaner** (BeautifulSoup, ~80 lines in `convert.py`)

Three targeted transforms applied before docling sees the file:

1. **Strip the hidden XBRL metadata block.** EDGAR embeds `<div style="display:none">` at the top of every filing with ~88–300 KB of machine-readable XBRL metadata. It is invisible in a browser and meaningless as document content. Removing it shrinks the cleaned HTML by ~20% and prevents it from appearing as noise in the output.

2. **Normalize table colspans.** For each `<table>`, the cleaner strips all `colspan` attributes so every cell occupies exactly one column, then removes columns that are empty in every row. This eliminates the phantom duplicate values that EDGAR's XBRL alignment colspans produce. Empty tables (no non-empty cells after cleanup) are removed entirely.

3. **Inject semantic heading tags.** EDGAR uses plain `<p>` and `<div>` elements for section labels. The cleaner detects text matching `PART I/II/III/IV` and `Item N[A-C].` patterns and replaces those elements with `<h2>` / `<h3>` tags. docling then emits proper `##` / `###` Markdown headings, which become the hard split boundaries for the heading-anchored chunker (see `Chunking and embedding` in [../docs/architecture.md](../docs/architecture.md)).

**Stage 2 — docling** (`DocumentConverter` with `compact_tables=True`)

Handles all prose: paragraphs, lists, in-document anchor links, and image placeholders. The cleaned HTML is passed as a `DocumentStream` so no temp files are written.

### Validated quality results (2024 filings)

| Company | Dup rows before | Dup rows after | Phantom tables | `##` headings | `###` headings |
|---------|----------------|----------------|----------------|---------------|----------------|
| AAPL    | 36.8%          | **1.5%**       | 0              | 4             | 23             |
| NVDA    | 28.8%          | **4.5%**       | 0              | 4             | 23             |
| MSFT    | 7.0%           | **2.3%**       | 0              | 4             | 30             |
| AMZN    | 42.0%          | **2.1%**       | 0              | 4             | 23             |
| GOOGL   | 33.4%          | **3.6%**       | 0              | 4             | 23             |

All 25 conversions (5 companies × 5 years) complete with `ConversionStatus.SUCCESS`.

### Residual duplication (1–5%)

The remaining matches are genuine data coincidences, not formatting artifacts — for example, money market funds where cost basis equals fair value, or commercial paper where carrying value equals face value. These appear in fair-value measurement tables as two separate, semantically distinct columns that happen to hold the same number. An LLM reading these tables for semantic Q&A handles them correctly.

### No new dependencies

`BeautifulSoup` is already in docling's dependency tree. `convert.py` imports nothing beyond docling and bs4.
