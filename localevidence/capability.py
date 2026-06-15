"""Capability gate: let a model answer only the task class it is competent at.

Empirically, a small local model (e.g. 14B) is reliable on retrieval-grounded
FACTUAL lookup (high grounding, ~0 hallucination) but unreliable on clinical
REASONING — management with comorbidities, test-ordering judgement, epidemiological
/ base-rate reasoning (frequent safety errors that scaffolding did not fix). So the
safe deployment is not to make it reason safely (shown brittle) but to GATE it: it
may synthesise only the class it handles reliably; ABOVE that it refuses and returns
the grounded evidence + an escalation note (the clinician still gets the useful
retrieval).

The SAME harness runs for any model — only the capability PROFILE (a deployment
config) differs. Capability is not the safety variable; the permitted-task config is.
Fails safe: unknown model tier -> 'small'; unclear task -> a reasoning class -> refuse.
"""
from __future__ import annotations

import os
import re
from typing import Callable, Optional

from . import inference

TASK_CLASSES = ["factual-lookup", "management", "test-ordering", "epidemiological", "emergency"]
REASONING_CLASSES = {"management", "test-ordering", "epidemiological", "emergency"}

# Which task classes each capability tier may SYNTHESISE an answer for.
PROFILES: dict[str, set] = {
    "small": {"factual-lookup"},                       # e.g. a 14B local model
    "large": {"factual-lookup"} | REASONING_CLASSES,  # a frontier / large model
}

_LARGE_MARKERS = re.compile(r"\b(70b|72b|405b|gpt-4|gpt-5|o[0-9]|opus|sonnet|claude|frontier)\b", re.I)


def tier_for_model(model_spec: Optional[str]) -> str:
    """Capability tier. Explicit LOCALEVIDENCE_MODEL_TIER wins; else a light name
    heuristic; else 'small' (fail safe — an unconfigured deployment is restricted)."""
    env = os.environ.get("LOCALEVIDENCE_MODEL_TIER", "").strip().lower()
    if env in ("small", "large"):
        return env
    return "large" if _LARGE_MARKERS.search(model_spec or "") else "small"


_CLASSIFY = (
    "Classify the clinical question into EXACTLY ONE task class:\n"
    "- factual-lookup: a single fact, definition, dose, threshold, or criterion that "
    "could be read straight from a source.\n"
    "- management: a treatment / management plan (especially with comorbidities).\n"
    "- test-ordering: whether or which test to order, or its pros/cons in a patient.\n"
    "- epidemiological: base rates, pre-test probability, or predictive-value reasoning.\n"
    "- emergency: acute, time-critical management.\n"
    "When in doubt between factual-lookup and anything else, choose the OTHER (reasoning) "
    "class. Reply with only the label.\n\nQuestion: ")


def classify_task(question: str, *, model: Optional[str] = None) -> str:
    """Model-based task classification. Fails safe to a reasoning class."""
    try:
        raw = inference.generate(_CLASSIFY + question, model=model).strip().lower()
    except inference.InferenceError:
        return "management"  # can't classify -> treat as reasoning -> refuse for small tier
    for c in REASONING_CLASSES:           # prefer a reasoning label if present (safe bias)
        if c in raw:
            return c
    if "factual" in raw:
        return "factual-lookup"
    return "management"                    # unrecognised -> fail safe to reasoning


def gate(question: str, *, model: Optional[str] = None, tier: Optional[str] = None) -> dict:
    tier = tier or tier_for_model(model)
    cls = classify_task(question, model=model)
    allowed = cls in PROFILES.get(tier, {"factual-lookup"})
    return {"task_class": cls, "tier": tier, "allowed": allowed}


def gated_answer(question: str, *, retrieve: Callable[[str, int], list[dict]],
                 model: Optional[str] = None, tier: Optional[str] = None, k: int = 8,
                 synth_fn: Optional[Callable] = None) -> dict:
    """Gate, then either synthesise (in-tier) or refuse-with-evidence (above-tier)."""
    g = gate(question, model=model, tier=tier)
    passages = list(retrieve(question, k))
    if g["allowed"]:
        synth = synth_fn or inference.synthesize_answer
        ans = synth(question, passages, model=model)
        return {**g, "disposition": "answered", "answer": ans["answer"],
                "passages": passages, "n_passages": len(passages)}
    note = (f"Refused: this is a '{g['task_class']}' question, which a '{g['tier']}'-"
            "capability model is not permitted to answer here — it requires a clinician "
            "or a more capable model. The retrieved evidence below is provided for you "
            "to reason from yourself.")
    return {**g, "disposition": "refused", "answer": None, "refusal": note,
            "passages": passages, "n_passages": len(passages)}
