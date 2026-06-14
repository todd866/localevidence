"""Drain the phone queue — the questions the PWA parked for the next deep run.

The `serve` backend appends novel questions to `ledger/queue.jsonl` (it returns
live evidence to the phone immediately but defers the full acquire-and-synthesise
pass). This module is the home-side drain: `queue run` replays each parked
question through the full `ask` loop, leaving an evidence pack per question ready
for synthesis (`answer`). Synthesis stays the agent-in-the-loop step.
"""

from __future__ import annotations

import json
from pathlib import Path

from . import config

QUEUE_PATH = config.ROOT / "ledger" / "queue.jsonl"


def read_queue(path: Path = QUEUE_PATH) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def append_queue(question: str, ts: str = "", path: Path = QUEUE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps({"question": question, "ts": ts}) + "\n")


def clear_queue(path: Path = QUEUE_PATH) -> int:
    items = read_queue(path)
    if path.exists():
        path.unlink()
    return len(items)


def list_queue(*, verbose: bool = True, path: Path = QUEUE_PATH) -> list[dict]:
    items = read_queue(path)
    if verbose:
        if not items:
            print("  queue empty")
        for i, it in enumerate(items, 1):
            print(f"  {i}. [{it.get('ts', '')}] {it.get('question', '')}")
    return items


def run_queue(*, top_n: int = 15, k_passages: int = 12, oa_only: bool = False,
              clear: bool = True, verbose: bool = True,
              path: Path = QUEUE_PATH) -> list[dict]:
    """Replay each queued question through the full `ask` loop.

    Leaves an evidence pack per question (synthesise each with `answer`). Clears
    the queue afterwards unless `clear=False`.
    """
    from .pipeline import ask
    items = read_queue(path)
    if not items:
        if verbose:
            print("  queue empty — nothing to run")
        return []
    results: list[dict] = []
    for i, it in enumerate(items, 1):
        q = (it.get("question") or "").strip()
        if not q:
            continue
        if verbose:
            print(f"\n=== queue [{i}/{len(items)}] {q}")
        try:
            res = ask(q, top_n=top_n, k_passages=k_passages,
                      oa_only=oa_only, verbose=verbose)
            results.append({"question": q, "evidence_pack": str(res.evidence_pack_path)})
        except Exception as e:
            if verbose:
                print(f"  ! failed: {type(e).__name__}: {e}")
            results.append({"question": q, "error": f"{type(e).__name__}: {e}"})
    if clear:
        clear_queue(path)
    if verbose:
        print(f"\n  drained {len(results)} queued question(s); "
              f"synthesise each pack with `answer`.")
    return results
