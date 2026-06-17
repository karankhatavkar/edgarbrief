# /// script
# requires-python = ">=3.12"
# dependencies = ["docling"]
# ///
from __future__ import annotations

from pathlib import Path

from docling.document_converter import DocumentConverter

DOWNLOADS_DIR = Path(__file__).resolve().parent / "downloads"
MARKDOWN_DIR = Path(__file__).resolve().parent / "markdown"

SKIP_PATTERNS = {"manifest.json"}


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

        result = converter.convert(src, raises_on_error=False)
        if result.status.value not in ("success", "partial_success"):
            print(f" FAILED ({result.status})")
            continue

        dest.write_text(result.document.export_to_markdown(), encoding="utf-8")
        print(f" done ({dest.stat().st_size // 1024} KB)")

    print(f"\nMarkdown files saved to: {MARKDOWN_DIR}")


if __name__ == "__main__":
    convert_all()
