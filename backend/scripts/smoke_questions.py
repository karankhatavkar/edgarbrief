"""Smoke-test the 10 example analyst questions against the live stack.

Runs each brief question through the real grounded path (``agent.run`` +
``build_grounded_answer``, mirroring ``chat.orchestrator`` without persistence)
against live Gemini + Supabase, then prints a per-question report: latency,
citation count, cited filings, and an answer preview.

    cd backend && uv run python scripts/smoke_questions.py

This is a manual harness, not a unit test — it makes real API/DB calls and needs
a populated backend/.env. It's the Phase 8 "smoke-test all 10 example questions"
and latency-review baseline. Streaming starts only after the agent run completes
(grounding is enforced inside the run), so the latency here IS the
time-to-first-token the analyst sees.
"""

import asyncio
import time

from pydantic_ai import UnexpectedModelBehavior

from app.assistant.agent import agent
from app.assistant.deps import DocumentAgentDeps
from app.assistant.outputs import build_grounded_answer
from app.database.session import async_session

# Verbatim from docs/brief.md. Question 10 must refuse to infer beyond filings.
QUESTIONS = [
    "Across Apple's 2021-2025 10-Ks, how did the revenue mix between iPhone, "
    "Services, Mac, iPad, and Wearables change, and which category appears to "
    "have contributed most to any mix shift?",
    "For Amazon, compare AWS operating income and margin against North America "
    "and International from 2021-2025. In which years did AWS appear to fund "
    "losses or weaker profitability elsewhere?",
    "How did NVIDIA describe demand drivers, customer concentration, and supply "
    "constraints for its Data Center business from fiscal 2021 through fiscal 2025?",
    "Across Microsoft's 2021-2025 filings, what changed in the way the company "
    "describes Azure, AI infrastructure, and cloud capacity constraints?",
    "For Alphabet, how did Google Search, YouTube ads, Google Network, "
    "subscriptions/platforms/devices, and Google Cloud revenue trends differ "
    "across the available 10-Ks?",
    "Which of the five companies added, removed, or materially changed "
    "risk-factor language related to AI, cloud infrastructure, export controls, "
    "supply chain concentration, or regulation between 2021 and 2025?",
    "For Apple and NVIDIA, what do the filings say about supplier concentration "
    "or dependence on third-party manufacturing, and did the wording become more "
    "or less urgent over time?",
    "Compare capital expenditures and purchase commitments for Microsoft, "
    "Alphabet, Amazon, and NVIDIA. What do the filings imply about the scale and "
    "timing of AI/cloud infrastructure investment?",
    "For each company, summarize the most important geographic revenue exposures "
    "disclosed in the latest 10-K, then identify any year-over-year changes that "
    "could matter to an analyst.",
    "If an analyst asks whether the filings prove that generative AI improved "
    "margins for any of these companies, what evidence exists in the corpus, and "
    "where should the bot refuse to infer beyond the filings?",
]

# Heuristic markers for Q10's "refuse to infer beyond the filings" behavior.
REFUSAL_MARKERS = (
    "not enough evidence",
    "no evidence",
    "insufficient",
    "do not prove",
    "does not prove",
    "cannot conclude",
    "cannot infer",
    "do not establish",
    "does not establish",
    "refuse",
)


async def run_one(question: str) -> dict:
    deps = DocumentAgentDeps(session_factory=async_session)
    start = time.perf_counter()
    try:
        result = await agent.run(question, deps=deps)
    except UnexpectedModelBehavior:
        return {
            "grounded": False,
            "elapsed": time.perf_counter() - start,
            "retrieved": len(deps.retrieved),
        }
    except Exception as error:
        # Don't let one bad turn abort the whole baseline (e.g. a turn that
        # exhausts the agent's request budget). Report and move on.
        return {
            "grounded": False,
            "elapsed": time.perf_counter() - start,
            "retrieved": len(deps.retrieved),
            "error": f"{type(error).__name__}: {error}",
        }
    grounded = build_grounded_answer(result.output, deps.retrieved)
    return {
        "grounded": True,
        "elapsed": time.perf_counter() - start,
        "answer": grounded.answer,
        "refused": grounded.refused,
        "passages": grounded.cited_passages,
        "retrieved": len(deps.retrieved),
    }


def fmt_passage(p) -> str:
    return f"{p.ticker} {p.fiscal_year} {p.filing_type} p{p.page}"


def _selected_indices(argv: list[str]) -> list[int]:
    """1-based question numbers from the CLI, or all of them by default.

    Usage: `python scripts/smoke_questions.py 6 7 8` to re-run a subset.
    """
    if not argv:
        return list(range(1, len(QUESTIONS) + 1))
    return [int(a) for a in argv]


async def main(argv: list[str]) -> None:
    indices = _selected_indices(argv)
    print(f"EdgarBrief smoke test — questions {indices}\n")
    runs = []  # (index, result)
    for i in indices:
        question = QUESTIONS[i - 1]
        print(f"[{i}/{len(QUESTIONS)}] {question[:88]}...")
        result = await run_one(question)
        runs.append((i, result))
        if not result["grounded"]:
            reason = result.get("error", "failed closed (no grounded answer)")
            print(
                f"   NO ANSWER — {reason} "
                f"[{result['elapsed']:.1f}s, retrieved {result['retrieved']}]\n"
            )
            continue
        cites = ", ".join(fmt_passage(p) for p in result["passages"]) or "—"
        print(
            f"   {result['elapsed']:.1f}s · {len(result['passages'])} citations · "
            f"refused={result['refused']}"
        )
        print(f"   cites: {cites}")
        print(f"   answer: {result['answer'][:200].strip()}...\n")

    grounded_n = sum(1 for _, r in runs if r["grounded"])
    latencies = [r["elapsed"] for _, r in runs]
    slow = [(i, f"{r['elapsed']:.1f}s") for i, r in runs if r["elapsed"] > 10]

    print("=" * 64)
    print("Summary")
    print(f"  grounded answers: {grounded_n}/{len(runs)}")
    q10 = next((r for i, r in runs if i == 10), None)
    if q10 is not None:
        q10_text = (q10.get("answer") or "").lower()
        q10_refuses = bool(q10.get("refused")) or any(m in q10_text for m in REFUSAL_MARKERS)
        print(f"  Q10 refuses to infer beyond filings: {'YES' if q10_refuses else 'NO — REVIEW'}")
    print(f"  latency: min {min(latencies):.1f}s · max {max(latencies):.1f}s · "
          f"mean {sum(latencies) / len(latencies):.1f}s")
    if slow:
        print(f"  slow turns (>10s): {slow}")


if __name__ == "__main__":
    import sys

    asyncio.run(main(sys.argv[1:]))
