"""The governance layer: monitor per-node behaviour and make every action attributable.

This closes the loop the operating point opens. `operating_point.decide` turns a
probability + a local dial into a deterministic action; this module:
  - composes that with the capability GATE (the gate decides WHETHER the model may
    estimate the probability at all; the dial decides the ACTION given the estimate);
  - persists every decision to an append-only per-node log, so "wants to MRI
    everyone" stops being an anecdote and becomes a measurable investigate-rate;
  - records the dial that produced each action, so a bad recommendation is
    attributable to a specific, version-controlled operating-point setting.

What a black box cannot offer: a per-node investigate-rate you can watch, and a
recommendation you can trace back to the exact cost/base-rate setting that caused it.

Caveat carried by design: estimating the probability is the soft, model-dependent
step (hence the gate guards it); the dial only governs the action given that
estimate. A well-set dial on a bad estimate still mis-targets — the value is that
the setting is explicit, bounded, and auditable, not that it is automatically right.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union

from . import config, inference, operating_point

_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


# ── per-node decision log (monitoring + attributability) ────────────────────

class DecisionLog:
    """Append-only JSONL of governed decisions, keyed by node."""

    def __init__(self, path: Optional[Union[str, Path]] = None):
        self.path = Path(path) if path else (
            config.PASSAGES_DIR.parent / "governance" / "decisions.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(record) + "\n")

    def records(self, node: Optional[str] = None) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if node is None or r.get("node") == node:
                out.append(r)
        return out

    def investigate_rate(self, node: Optional[str] = None) -> float:
        """Fraction of decisions that recommended investigating — the 'MRI-everyone'
        signal made measurable per node."""
        rs = self.records(node)
        if not rs:
            return 0.0
        return round(sum(1 for r in rs if r.get("action") == "investigate") / len(rs), 3)

    def summary(self, node: Optional[str] = None) -> dict:
        rs = self.records(node)
        counts: dict[str, int] = {}
        for r in rs:
            counts[r.get("action")] = counts.get(r.get("action"), 0) + 1
        n = len(rs)
        active = sum(v for k, v in counts.items() if k in ("investigate", "escalate"))
        return {"n": n, "counts": counts,
                "investigate_rate": round(counts.get("investigate", 0) / n, 3) if n else 0.0,
                "active_rate": round(active / n, 3) if n else 0.0}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def govern(op: operating_point.OperatingPoint, prob: Optional[float], *,
           log: Optional[DecisionLog] = None, question: Optional[str] = None,
           task_class: Optional[str] = None, tier: Optional[str] = None,
           at: Optional[str] = None) -> dict:
    """Apply the deterministic dial to a probability and record the decision (with
    its inputs + the dial) to the log, for monitoring and attribution."""
    decision = operating_point.decide(op, prob)
    record = {**decision, "question": question, "task_class": task_class,
              "tier": tier, "at": at or _now()}
    if log is not None:
        log.append(record)
    return record


# ── probability estimation (the soft, gated, model-dependent step) ──────────

def estimate_probability(question: str, *, retrieve: Optional[Callable] = None,
                         model: Optional[str] = None) -> Optional[float]:
    """Ask the model for a pre-test probability of the dangerous condition, grounded
    in retrieved passages when available. Returns a float in [0,1], or None if the
    model is unavailable or gives no usable number (caller falls back to base rate).
    This is deliberately the ONLY model-in-the-loop step — the gate guards it."""
    passages = list(retrieve(question, 6)) if retrieve else []
    ctx = inference._format_passages(passages) if passages else ""
    prompt = ("Estimate the PRE-TEST PROBABILITY, as a single number between 0 and 1, "
              "that the most dangerous condition implied by the question is actually "
              "present in this patient. Reply with ONLY the number.\n\n"
              + (f"Evidence:\n{ctx}\n\n" if ctx else "") + f"Question: {question}")
    try:
        raw = inference.generate(prompt, model=model)
    except inference.InferenceError:
        return None
    nums = [float(x) for x in _NUM_RE.findall(raw)]
    for n in nums:
        if 0.0 <= n <= 1.0:
            return n
    for n in nums:               # tolerate a percentage ("12%")
        if 1.0 < n <= 100.0:
            return n / 100.0
    return None


def _default_gate(question: str, *, model: Optional[str] = None) -> dict:
    from . import capability
    return capability.gate(question, model=model)


def governed_answer(question: str, op: operating_point.OperatingPoint, *,
                    retrieve: Callable, model: Optional[str] = None,
                    log: Optional[DecisionLog] = None,
                    gate_fn: Optional[Callable] = None,
                    estimate_fn: Optional[Callable] = None,
                    at: Optional[str] = None) -> dict:
    """Full governed path: GATE (may the model reason here?) -> estimate the
    probability -> DETERMINISTIC dial decides the action -> log it. If the gate
    refuses, no decision is made or logged (a probability from an untrusted model
    must not drive an action)."""
    g = (gate_fn or _default_gate)(question, model=model)
    if not g.get("allowed"):
        return {"disposition": "refused", "gate": g, "operating_point": op.to_dict(),
                "refusal": (f"Refused: a '{g.get('task_class')}' question needs a capable "
                            "enough model or a clinician to estimate the probability; the "
                            "local operating point governs the action only once a trustworthy "
                            "estimate exists.")}
    prob = (estimate_fn or estimate_probability)(question, retrieve=retrieve, model=model)
    record = govern(op, prob, log=log, question=question,
                    task_class=g.get("task_class"), tier=g.get("tier"), at=at)
    return {"disposition": "decided", "gate": g, "decision": record, "estimated_prob": prob}
