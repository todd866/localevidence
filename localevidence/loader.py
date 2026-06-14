"""The loader — self-play on simulated questions to get the system ready.

Runs the full `ask` loop over a question bank in the user's domains, so the
corpus, the persistent passage index, and the knowledge ledger are warm before a
real question ever arrives. Idempotent (skips questions already in the ledger),
politely paced (the acquisition tiers have quotas), and doubling as an eval
harness — the aggregate coverage tells you where the corpus is thin.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from . import config, pipeline
from .ledger import Ledger


def load_bank(path: Optional[Path] = None) -> list[dict]:
    import yaml
    p = Path(path or (config.ROOT / "data" / "question_bank.yaml"))
    items = yaml.safe_load(p.read_text()) or []
    out = []
    for it in items:
        if isinstance(it, str):
            out.append({"question": it, "topic": "", "queries": []})
        elif isinstance(it, dict) and it.get("question"):
            out.append({"question": it["question"], "topic": it.get("topic", ""),
                        "queries": it.get("queries") or []})
    return out


def run_bank(
    bank: list[dict],
    *,
    topic: Optional[str] = None,
    limit: int = 0,
    top_n: int = 12,
    max_per_query: int = 70,
    k_passages: int = 12,
    oa_only: bool = False,
    force: bool = False,
    pace_s: float = 2.0,
    verbose: bool = True,
) -> dict:
    """Run the bank through `ask`. Returns an aggregate report."""
    if topic:
        bank = [b for b in bank if b.get("topic") == topic]
    if limit > 0:
        bank = bank[:limit]

    led = Ledger()
    done = {e["question"].strip().lower() for e in led.entries}

    results: list[dict] = []
    skipped = 0
    for i, item in enumerate(bank, 1):
        q = item["question"]
        if not force and q.strip().lower() in done:
            skipped += 1
            if verbose:
                print(f"\n[{i}/{len(bank)}] SKIP (already in ledger): {q[:70]}")
            continue
        if verbose:
            print(f"\n[{i}/{len(bank)}] ({item.get('topic','')}) {q}")
        try:
            res = pipeline.ask(
                q,
                extra_queries=item.get("queries") or None,
                top_n=top_n, max_per_query=max_per_query, k_passages=k_passages,
                oa_only=oa_only, verbose=verbose)
            results.append(res.summary)
        except Exception as e:
            if verbose:
                print(f"  load: question failed ({type(e).__name__}: {e})")
            results.append({"question": q, "error": str(e)})
        if pace_s and i < len(bank):
            time.sleep(pace_s)

    ok = [r for r in results if "error" not in r]
    agg = {
        "questions_run": len(results),
        "skipped_already_done": skipped,
        "failed": len(results) - len(ok),
        "total_newly_pulled": sum(r.get("newly_pulled", 0) for r in ok),
        "total_papers_indexed": sum(r.get("papers_indexed", 0) for r in ok),
        "thin_topics": [r["question"][:60] for r in ok if r.get("papers_indexed", 0) < 3],
        "passage_store": (ok[-1].get("passage_store") if ok else None),
        "ledger": led.stats(),
    }
    if verbose:
        import json
        print("\n=== load complete ===")
        print(json.dumps(agg, indent=2))
    return agg
