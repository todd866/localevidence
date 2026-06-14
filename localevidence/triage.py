"""Triage: rank candidates by relevance x evidence tier, pick what to acquire.

This is the cheap gate that protects the night (and any rate-limited acquisition
budget): embed abstracts (free, no downloads), score, dedupe against what the
local library already holds, and select only the top-N missing papers for
full-text acquisition.

The triage decision is returned as data so the pipeline can log it (auditable:
why each paper was chosen or skipped).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import config, embedding
from .discovery import Candidate


# Tier multipliers applied to the semantic relevance score. Relevance stays
# dominant (we never want an on-tier but off-topic paper); tier breaks ties and
# nudges guidelines/SRs up among comparably-relevant candidates.
_TIER_BOOST = {
    "guideline": 1.30,
    "systematic-review": 1.22,
    "rct": 1.12,
    "cohort": 1.06,
    "review": 1.04,
    "article": 1.00,
    "other": 0.96,
}


@dataclass
class TriageResult:
    ranked: list[Candidate]                 # all candidates, scored + sorted
    to_acquire: list[Candidate] = field(default_factory=list)   # top-N, not in library
    in_library: list[Candidate] = field(default_factory=list)   # relevant, already held
    below_floor: int = 0                    # dropped as off-topic


def _library_lookup(c: Candidate):
    """Return the library record for a candidate if held, else None."""
    try:
        from .library import find  # self-contained local library
    except Exception:
        return None
    rec = None
    if c.doi:
        rec = find(doi=c.doi)
    if not rec and c.pmid:
        rec = find(pmid=c.pmid)
    return rec


def triage(
    question: str,
    candidates: list[Candidate],
    *,
    top_n: int = 25,
    relevance_floor: float = 0.25,
    require_doi: bool = True,
    verbose: bool = True,
) -> TriageResult:
    """Score and select. `top_n` caps how many *new* papers we will fetch."""
    if not candidates:
        return TriageResult(ranked=[])

    qvec = embedding.embed([question])[0]
    abstract_texts = [f"{c.title}. {c.abstract}" for c in candidates]
    mat = embedding.embed(abstract_texts, show_progress=verbose and len(candidates) > 200)
    rel = embedding.cosine(qvec, mat)

    for c, r in zip(candidates, rel):
        c.relevance = float(r)
        c.tier = config.classify_tier(c.title, c.abstract, c.type)
        c.score = float(r) * _TIER_BOOST.get(c.tier, 1.0)

    ranked = sorted(candidates, key=lambda c: c.score, reverse=True)

    # Mark library membership for the relevant head only (cheap; avoids a DB
    # hit for every off-topic word-matcher).
    result = TriageResult(ranked=ranked)
    picked = 0
    for c in ranked:
        if c.relevance < relevance_floor:
            result.below_floor += 1
            continue
        rec = _library_lookup(c)
        if rec:
            c.in_library = True
            c.library_slug = rec.get("slug", "")
            result.in_library.append(c)
            continue
        if require_doi and not c.doi:
            continue   # can't acquire without a DOI; leave for the library prefilter
        if picked < top_n:
            result.to_acquire.append(c)
            picked += 1

    if verbose:
        print(f"  triage: {len(result.to_acquire)} to acquire, "
              f"{len(result.in_library)} already in library, "
              f"{result.below_floor} below relevance floor "
              f"(floor={relevance_floor}, top_n={top_n})")
    return result
