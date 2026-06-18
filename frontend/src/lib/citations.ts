/**
 * A cited filing passage — the unit of trust in EdgarBrief.
 *
 * The exact shape arrives two ways and must stay identical to the backend's
 * `SourcePassage`: live on the chat stream's `8:` frame, and on
 * `GET /threads/{id}/messages` when a thread is reloaded.
 */
export interface SourcePassage {
  passage_index: number;
  chunk_id: string;
  ticker: string;
  company: string;
  fiscal_year: number;
  filing_type: string;
  filing_date: string | null;
  section: string | null;
  page: number | null;
  source_url: string;
  excerpt: string;
}

/** e.g. "AAPL · 10-K · FY2024" — the filing a passage comes from. */
export function filingLabel(p: SourcePassage): string {
  return `${p.ticker} · ${p.filing_type} · FY${p.fiscal_year}`;
}

/** e.g. "Item 7 · p.34" — where in the filing, omitting parts we don't have. */
export function locationLabel(p: SourcePassage): string {
  return [p.section, p.page != null ? `p.${p.page}` : null]
    .filter(Boolean)
    .join(" · ");
}
