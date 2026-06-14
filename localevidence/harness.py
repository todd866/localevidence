"""A grounded-answer harness that pushes a small local model toward frontier-grade
clinical answers — by structure, not scale.

The bet of the whole tool is that the corpus and the grounding carry the quality
and the safety, not the model's raw capability. This module makes that concrete:
around a modest local model (e.g. qwen2.5:14b on a laptop) it wraps a multi-stage
loop that a frontier model would do implicitly —

    retrieve  ->  (query-expand)  ->  draft  ->  self-critique vs the passages
              ->  revise  ->  programmatic citation verification  ->  report

Each model step is a free, on-device call, so the harness can be run as hard as
you like. Citation verification is deterministic (no model), so "is every claim
actually tied to a retrieved passage?" is checked by code, not vibes.

Model calls go through inference.generate (swappable backend); retrieval is
injected, so the whole loop is unit-testable without a model or a corpus.
"""
from __future__ import annotations

import re
from typing import Callable, Optional, Sequence

from . import inference

CITE_RE = re.compile(r"\[([a-z0-9][\w.\-]*#\d+)\]", re.I)
_SENT_RE = re.compile(r"(?<=[.!?])\s+")


# ── deterministic citation verification (no model) ──────────────────────────

def verify_citations(answer: str, passage_ids: Sequence[str]) -> dict:
    """Check every [slug#n] in the answer against the retrieved passage ids, and
    measure how much of the answer is actually grounded."""
    ids = set(passage_ids)
    cited = CITE_RE.findall(answer)
    valid = [c for c in cited if c in ids]
    invalid = [c for c in cited if c not in ids]
    sentences = [s for s in _SENT_RE.split(answer.strip()) if s.strip()]
    grounded = [s for s in sentences if any(c in ids for c in CITE_RE.findall(s))]
    coverage = round(len(grounded) / len(sentences), 3) if sentences else 0.0
    return {"cited": cited, "valid": sorted(set(valid)),
            "invalid": sorted(set(invalid)),
            "n_sentences": len(sentences), "n_grounded": len(grounded),
            "coverage": coverage, "hallucinated_citations": len(set(invalid))}


# ── model stages (each a single local call) ─────────────────────────────────

def expand_queries(question: str, *, model: Optional[str] = None,
                   n: int = 3) -> list[str]:
    """Ask the model for focused retrieval sub-queries to broaden grounding."""
    prompt = (f"A clinician asks: {question}\n\nList up to {n} short, distinct "
              "search queries that would retrieve the evidence needed to answer "
              "well (e.g. specific drugs, thresholds, complications). One per line, "
              "no numbering, no prose.")
    try:
        raw = inference.generate(prompt, model=model)
    except inference.InferenceError:
        return []
    qs = [re.sub(r"^[\-\*\d.\)\s]+", "", ln).strip() for ln in raw.splitlines()]
    return [q for q in qs if 3 < len(q) < 120][:n]


def draft_answer(question: str, passages: Sequence[dict], *,
                 model: Optional[str] = None) -> str:
    return inference.synthesize_answer(question, passages, model=model)["answer"]


def critique(question: str, draft: str, passages: Sequence[dict], *,
             model: Optional[str] = None) -> str:
    prompt = (
        f"Question: {question}\n\nEvidence passages:\n"
        f"{inference._format_passages(passages)}\n\nDraft answer:\n{draft}\n\n"
        "Critique the draft STRICTLY against the passages. List, as terse bullet "
        "points, every: (a) claim not supported by any passage, (b) missing "
        "clinically important caveat the passages do support, (c) citation that "
        "does not match a passage id. If the draft is fully grounded and complete, "
        "reply exactly: OK.")
    return inference.generate(prompt, model=model)


def revise(question: str, draft: str, crit: str, passages: Sequence[dict], *,
           model: Optional[str] = None) -> str:
    prompt = (
        f"Question: {question}\n\nEvidence passages:\n"
        f"{inference._format_passages(passages)}\n\nDraft answer:\n{draft}\n\n"
        f"Critique to address:\n{crit}\n\n"
        "Rewrite the answer to fix every point in the critique. Use ONLY the "
        "passages, cite each claim with its [slug#n] id, and drop any claim the "
        "passages do not support. Keep it concise and clinically precise.")
    return inference.generate(prompt, system=inference._SYSTEM, model=model)


# ── the loop ────────────────────────────────────────────────────────────────

def grounded_answer(question: str, *,
                    retrieve: Callable[[str, int], list[dict]],
                    model: Optional[str] = None, k: int = 8,
                    expand: bool = True, reflect: bool = True,
                    max_passages: int = 12) -> dict:
    """Run the full harness. `retrieve(query, k) -> [passage dicts]` is injected
    (wrap PassageIndex.search at the call site). Returns the answer plus a full
    grounding report and every intermediate stage for inspection."""
    stages: list[str] = []

    # 1. retrieve (+ optional model-proposed sub-queries, de-duplicated by id)
    passages = list(retrieve(question, k))
    stages.append("retrieve")
    if expand:
        seen = {p["id"] for p in passages}
        for sq in expand_queries(question, model=model):
            for p in retrieve(sq, max(2, k // 2)):
                if p["id"] not in seen and len(passages) < max_passages:
                    seen.add(p["id"]); passages.append(p)
        stages.append("expand")
    pids = [p["id"] for p in passages]

    if not passages:
        return {"answer": "No supporting passages were retrieved; cannot answer "
                          "from the local corpus.", "grounded": False,
                "passages": [], "stages": stages, "model": model or inference.DEFAULT_MODEL}

    # 2. draft
    draft = draft_answer(question, passages, model=model)
    stages.append("draft")
    answer, crit = draft, None

    # 3. self-critique + revise
    if reflect:
        crit = critique(question, draft, passages, model=model)
        stages.append("critique")
        if crit.strip().upper() != "OK":
            answer = revise(question, draft, crit, passages, model=model)
            stages.append("revise")

    # 4. deterministic citation verification
    report = verify_citations(answer, pids)
    stages.append("verify")

    return {"question": question, "answer": answer, "draft": draft,
            "critique": crit, "grounding": report, "grounded": report["coverage"] > 0,
            "passages": passages, "n_passages": len(passages), "stages": stages,
            "model": model or inference.DEFAULT_MODEL}
