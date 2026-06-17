"""Load source documents from data/markdown/ into the source_documents table.

Run from backend/:
    uv run python ingest/load_source_documents.py

Idempotent: rows already present (matched by accession_number) are skipped,
so re-running after adding new markdown files is safe.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.database.models.source_document import SourceDocument

REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "data" / "downloads" / "manifest.json"
MARKDOWN_DIR = REPO_ROOT / "data" / "markdown"

COMPANY_NAMES: dict[str, str] = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corporation",
    "NVDA": "NVIDIA Corporation",
    "AMZN": "Amazon.com, Inc.",
    "GOOGL": "Alphabet Inc.",
}


def _db_url() -> str:
    url = str(settings.database_url)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def main() -> None:
    filings: list[dict] = json.loads(MANIFEST_PATH.read_text())["filings"]

    engine = create_engine(_db_url())
    inserted = skipped = missing = 0

    with Session(engine) as session:
        for f in filings:
            ticker = f["ticker"]
            label = f"{ticker} {f['report_date'][:4]}"
            accession = f["accession_number"]

            already_exists = session.scalar(
                select(SourceDocument.id).where(
                    SourceDocument.accession_number == accession
                )
            )
            if already_exists:
                print(f"  SKIP  {label}")
                skipped += 1
                continue

            md_path = MARKDOWN_DIR / Path(f["local_path"]).with_suffix(".md")
            if not md_path.exists():
                print(f"  MISS  {label}  — no markdown at {md_path.name}")
                missing += 1
                continue

            markdown = md_path.read_text(encoding="utf-8")

            session.add(
                SourceDocument(
                    ticker=ticker,
                    company=COMPANY_NAMES[ticker],
                    cik=f["cik"],
                    filing_type=f["form"],
                    filing_date=date.fromisoformat(f["filing_date"]),
                    report_date=date.fromisoformat(f["report_date"]),
                    fiscal_year=int(f["report_date"][:4]),
                    accession_number=accession,
                    source_url=f["source_url"],
                    markdown=markdown,
                    word_count=len(markdown.split()),
                )
            )
            try:
                session.commit()
            except IntegrityError:
                session.rollback()
                print(f"  SKIP  {label}  (concurrent insert)")
                skipped += 1
                continue

            print(f"  OK    {label}  ({len(markdown.split()):,} words)")
            inserted += 1

    print(f"\nDone — {inserted} inserted, {skipped} skipped, {missing} missing markdown.")


if __name__ == "__main__":
    main()
