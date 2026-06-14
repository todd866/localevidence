"""Long-form local eval: run the grounded harness over many clinical questions
on-device and measure how much the harness lifts a small model.

The metric that matters here is GROUNDING, computed deterministically (no judge):
- coverage: fraction of answer sentences tied to a real retrieved passage,
- hallucinated_citations: [ids] the model cited that were never retrieved.

A frontier model isn't needed to score this — it's arithmetic over the citation
ids. Run with `--baseline` to also produce the one-shot answer (no expand /
critique / revise) on the same passages, so the harness's contribution is
isolated. Because the model is local and free, run it over hundreds of questions.
"""
from __future__ import annotations

from typing import Callable, Optional, Sequence

from . import harness, inference


def baseline_answer(question: str, passages: Sequence[dict], *,
                    model: Optional[str] = None) -> dict:
    """One-shot answer on the SAME passages — the no-harness control."""
    ans = inference.synthesize_answer(question, passages, model=model)["answer"]
    return {"answer": ans,
            "grounding": harness.verify_citations(ans, [p["id"] for p in passages])}


def _g(r: dict) -> dict:
    return r["grounding"] if "grounding" in r else r


def summarize(results: Sequence[dict]) -> dict:
    """Aggregate grounding metrics over a set of per-question grounding reports."""
    gs = [_g(r) for r in results]
    n = len(gs) or 1
    return {
        "n": len(gs),
        "mean_coverage": round(sum(g["coverage"] for g in gs) / n, 3),
        "mean_hallucinated": round(sum(g["hallucinated_citations"] for g in gs) / n, 3),
        "fully_grounded": sum(1 for g in gs if g["coverage"] >= 0.99),
        "any_hallucination": sum(1 for g in gs if g["hallucinated_citations"] > 0),
    }


def lift(harness_results: Sequence[dict], baseline_results: Sequence[dict]) -> dict:
    """The harness's contribution: harness summary vs baseline summary."""
    h, b = summarize(harness_results), summarize(baseline_results)
    return {"baseline": b, "harness": h,
            "coverage_gain": round(h["mean_coverage"] - b["mean_coverage"], 3),
            "hallucination_reduction": round(b["mean_hallucinated"] - h["mean_hallucinated"], 3)}


def run_eval(questions: Sequence[str], *, retrieve: Callable[[str, int], list[dict]],
             model: Optional[str] = None, k: int = 8, baseline: bool = False,
             on_result: Optional[Callable[[int, dict], None]] = None) -> dict:
    """Run the harness (and optionally the one-shot baseline) over `questions`."""
    h_results, b_results, rows = [], [], []
    for i, q in enumerate(questions):
        h = harness.grounded_answer(q, retrieve=retrieve, model=model, k=k)
        row = {"question": q, "answer": h["answer"], "stages": h["stages"],
               "harness": h["grounding"]}
        h_results.append(h)
        if baseline and h["passages"]:
            b = baseline_answer(q, h["passages"], model=model)
            row["baseline"] = b["grounding"]
            b_results.append(b)
        rows.append(row)
        if on_result:
            on_result(i, row)
    out = {"rows": rows, "model": model or inference.DEFAULT_MODEL,
           "summary": summarize(h_results)}
    if baseline and b_results:
        out["lift"] = lift(h_results, b_results)
    return out
