# Phase 8 — Pilot readiness notes

Status as of 2026-06-19. EdgarBrief is ready for a pilot **with the known
limitations below**. Local setup, corpus seeding, structured logging, and chat
persistence are in place; 9/10 example questions return grounded, cited answers
and the grounding contract (refuse to invent) holds.

## Smoke test — 10 example brief questions

Harness: `cd backend && uv run python scripts/smoke_questions.py` (append question
numbers to run a subset, e.g. `... 6 7 8`). Runs each question through the real
grounded path against live Gemini + Supabase. Run on 2026-06-19:

| # | Question | Result | Latency | Citations |
|---|----------|--------|---------|-----------|
| 1 | Apple revenue mix 2021–25 | grounded | 19.3s | 5 |
| 2 | Amazon AWS vs NA/Intl | grounded | 13.1s | 3 |
| 3 | NVIDIA Data Center | grounded | 24.7s | 12 |
| 4 | Microsoft Azure/AI | grounded | 80.4s | 6 |
| 5 | Alphabet revenue lines | grounded | 35.0s | 8 |
| 6 | 5-company risk-factor changes | **failed** | — | request budget exhausted (run 1) / transient 503 after 172s (run 2) |
| 7 | Apple + NVIDIA suppliers | grounded | 20.0s | 5 |
| 8 | 4-company capex | grounded | 28.5s | 6 |
| 9 | Geographic revenue exposure | grounded | 28.4s | 3 |
| 10 | Generative-AI margins | grounded — **correctly refuses** | 20.9s | 5 |

9/10 grounded with citations. Q10 correctly refuses to infer beyond the filings
("the filings do not contain evidence that generative AI has definitively improved
margins…") — the brief's key trust requirement.

## Known limitations (accepted for pilot)

1. **Latency / time-to-first-token: 13–80s for typical queries.** Grounding is
   enforced *inside* the agent run before any token streams, so a confident-but-
   unsupported answer can never reach the analyst. Time-to-first-token therefore
   ≈ full turn time. This is intentional (trust over speed). Follow-up to improve
   *perceived* latency without weakening the contract: live agent-progress events
   (see `docs/frontend-observations.md` #3).

2. **Very broad multi-company questions may fail or time out.** Questions that
   sweep all five companies (e.g. Q6) make 50+ tool/LLM calls, exhaust the agent's
   default request budget (`request_limit=50`), run ~170s, and are exposed to
   transient Gemini 503s — there is no retry/backoff today. Workaround for pilot:
   narrow the question (fewer companies or years). Deferred follow-up: a
   configurable usage limit + transient-error retry/backoff.

3. **Citation page numbers are often absent** (the chip shows "page —"). Ingestion
   only records a page where the source markdown carried one. Cosmetic — the
   filing, section, and excerpt still identify and verify the source.

## Verified for pilot

- **Chat history persists across sessions.** A persist→reload round-trip through
  the real `thread_db` helpers and live schema returns both messages and
  rehydrated citations (filing metadata + excerpt). See item 4 in
  `docs/todos.md`.
- **~40-user scale / no single-user shortcuts.** Per-request auth
  (`app/auth/dependencies.py`), per-request user DB client
  (`app/api/deps.py`), per-request async sessions (`app/database/session.py`),
  per-turn agent state (`DocumentAgentDeps`). Shared singletons (anon/service
  Supabase clients, Gemini embed client) are stateless and lock-guarded. No
  hardcoded user ids or dev shortcuts.
- **Structured logging for failed turns.** `structlog` emits `request.completed`
  (with a per-request `request_id`) plus `turn.started` / `turn.completed` /
  `turn.grounding_failed` / `turn.failed` / `turn.persist_failed`. A retrieval/
  LLM/DB error mid-run degrades to a controlled error frame (no 500 leak); a
  post-stream persistence failure is logged rather than dropped silently.
  Configure with `LOG_LEVEL` and `LOG_JSON` (set `LOG_JSON=true` in prod).
