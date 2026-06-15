"""Defence-in-depth safety layer, built from the empirical failure catalogue.

The reasoning eval showed a small local model fails on clinical REASONING, and that
prompting it to do *more* makes it MORE confidently wrong. So safety here is
constraint + verification + abstention, not more generation:

    triage (match landmines)  ->  inject the matched rules as HARD constraints
      ->  answer  ->  safety-critic screens the answer vs the rules' violation-checks
      ->  one corrective revise if violated; if a CRITICAL rule is still violated,
          abstain from a confident answer (flag + "verify with a senior clinician /
          the local guideline").

`safety_rules.json` is human-verified and doubles as both the rule INJECTED
(prevention) and the violation-checks the critic SCREENS for (detection).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Callable, Optional, Sequence

from . import inference

_RULES_PATH = Path(__file__).resolve().parent / "safety_rules.json"


def load_catalogue(path: Optional[Path] = None) -> list[dict]:
    return json.loads((path or _RULES_PATH).read_text())


def _rule_cue(r: dict) -> str:
    return r.get("cue") or (f"{r.get('category', '')}: "
                            f"{' '.join(r.get('triggers', [])[:6])}. {r.get('rule', '')[:140]}")


def _default_embedder(texts):
    from .embedding import embed
    return embed(texts)


def match_rules(question: str, catalogue: Sequence[dict], *, semantic: bool = True,
                embedder: Optional[Callable] = None, threshold: float = 0.45) -> list[dict]:
    """Which landmines apply. Keyword triggers (precise) UNION semantic cue-match
    (catches paraphrase / related conditions that brittle keywords missed). Semantic
    is best-effort — if embedding fails, keyword match still stands. Over-matching
    here is benign: the safety-critic just runs an extra rule's checks (mostly NO)."""
    q = question.lower()
    hit_ids = {r["id"] for r in catalogue if any(t.lower() in q for t in r.get("triggers", []))}
    if semantic:
        try:
            import numpy as np
            emb = embedder or _default_embedder
            qv = np.asarray(emb([question])[0])
            cv = np.asarray(emb([_rule_cue(r) for r in catalogue]))
            sims = (cv @ qv).tolist()
            hit_ids |= {catalogue[i]["id"] for i in range(len(catalogue)) if sims[i] >= threshold}
        except Exception:
            pass
    return [r for r in catalogue if r["id"] in hit_ids]  # catalogue order


def tier_of(rules: Sequence[dict]) -> str:
    tiers = {r.get("tier") for r in rules}
    return "critical" if "critical" in tiers else ("high" if "high" in tiers else "standard")


def rules_constraint_text(rules: Sequence[dict]) -> str:
    if not rules:
        return ""
    return ("HARD SAFETY RULES — you MUST follow every one; they override anything "
            "else:\n" + "\n".join(f"- {r['rule']}" for r in rules))


def safety_critic(question: str, answer: str, rules: Sequence[dict], *,
                  model: Optional[str] = None) -> list[dict]:
    """Screen the answer against the matched rules' violation-checks. Recognition,
    not generation (the safe operation for a small model). Returns flagged
    violations. If the critic can't run, fail SAFE (return an 'unknown' marker)."""
    checks = [(r["id"], r.get("tier", "high"), c)
              for r in rules for c in r.get("violation_checks", [])]
    if not checks:
        return []
    numbered = "\n".join(f"{i + 1}. {c}" for i, (_, _, c) in enumerate(checks))
    prompt = (
        f"Question:\n{question}\n\nAnswer to screen:\n{answer}\n\n"
        "Below are specific DANGEROUS patterns. For EACH, decide whether the answer "
        "commits it. Reply with exactly one line per item as 'N: YES' (it commits "
        "this) or 'N: NO', nothing else.\n\n" + numbered)
    try:
        raw = inference.generate(prompt, model=model)
    except inference.InferenceError:
        return [{"rule_id": "_critic_unavailable", "tier": "critical",
                 "check": "safety critic could not run", "violated": None}]
    verdicts: dict[int, bool] = {}
    for line in raw.splitlines():
        m = re.match(r"\s*(\d+)\s*[:.\)]\s*(YES|NO)", line, re.I)
        if m:
            verdicts[int(m.group(1))] = m.group(2).upper().startswith("Y")
    return [{"rule_id": rid, "tier": tier, "check": c, "violated": True}
            for i, (rid, tier, c) in enumerate(checks) if verdicts.get(i + 1)]


def guarded_answer(question: str, *, retrieve, answer_fn: Callable,
                   model: Optional[str] = None, k: int = 8,
                   catalogue: Optional[Sequence[dict]] = None) -> dict:
    """Defence-in-depth wrapper: match -> inject -> answer -> critic -> abstain/serve.
    `answer_fn` must accept a `constraints` kwarg (e.g. harness.reasoning_answer)."""
    cat = catalogue if catalogue is not None else load_catalogue()
    rules = match_rules(question, cat)
    tier = tier_of(rules)
    constraints = rules_constraint_text(rules)

    out = answer_fn(question, retrieve=retrieve, model=model, k=k, constraints=constraints)
    violations = safety_critic(question, out["answer"], rules, model=model)
    real = [v for v in violations if v.get("violated")]

    # one corrective pass if the critic flagged real violations
    if real:
        fix = ("Your answer violated these safety rules:\n"
               + "\n".join(f"- {v['check']}" for v in real)
               + "\n\nRewrite it to comply with the HARD SAFETY RULES; remove or "
                 "correct every violating statement.")
        try:
            out2 = answer_fn(question, retrieve=retrieve, model=model, k=k,
                             constraints=constraints + "\n\n" + fix)
            recheck = safety_critic(question, out2["answer"], rules, model=model)
            real2 = [v for v in recheck if v.get("violated")]
            if len(real2) < len(real):
                out, violations, real = out2, recheck, real2
        except inference.InferenceError:
            pass

    unknown = any(v.get("violated") is None for v in violations)
    crit_unresolved = [v for v in real if v.get("tier") == "critical"]
    if crit_unresolved or unknown:
        disposition = "abstain"
    elif real:
        disposition = "flagged"
    else:
        disposition = "served"

    note = None
    if disposition != "served":
        note = ("This answer touches a high-risk area where a small local model is "
                "unreliable and the safety screen flagged unresolved concerns. Do not "
                "act on it without verifying against the local guideline and a senior "
                "clinician.")

    return {"question": question, "answer": out["answer"], "tier": tier,
            "rules_applied": [r["id"] for r in rules], "violations": real,
            "disposition": disposition, "safety_note": note,
            "grounding": out.get("grounding"), "stages": out.get("stages"),
            "passages": out.get("passages", []),
            "n_passages": out.get("n_passages", len(out.get("passages", []))),
            "model": model or inference.DEFAULT_MODEL}
