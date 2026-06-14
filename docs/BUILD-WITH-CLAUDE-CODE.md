# Running LocalEvidence with Claude Code

LocalEvidence is designed to be operated by a capable coding agent. This is the
operating manual: the synthesis loop the agent closes, and the extension tasks
you hand it.

## The synthesis loop (the one step that isn't automated)

`ask` does everything up to a grounded **evidence pack**; it does *not* invent the
answer. Synthesis is the agent, in the loop:

```
1. python3 -m localevidence ask "<question>" -q "<focused query>" --top-n 15
      → projects/<slug>/runs/<run_id>/evidence-pack.md
2. The agent reads the pack (ranked, cited passages + coverage + gaps) and
   writes a cited answer to <run_dir>/answer.md, following docs/answer-style.md.
3. python3 -m localevidence answer --project <slug> --confidence high
      → folds the answer + cited DOIs into the ledger entry.
```

After step 3 the question is *worked*: a future similar question finds it via the
ledger and reuses or refreshes it instead of starting over. This deliberate
human/agent-in-the-loop synthesis — rather than a metered API call — is what lets
you spend a lavish token budget per question and audit the reasoning.

## Why an agent, not an API

The structural edge is the **compute asymmetry**: a personal tool can spend far
more per question than a product can spend per user. Plough through mediocre
first-pass retrieval with more passes, a wider acquisition net, and careful
reading — overnight, on your topics. The agent is how you spend that budget.

## Extension tasks to hand the agent

These are scoped, self-contained, and exactly what this repo is shaped for:

- **Rebuild the acquisition tier you want.** Implement one `fetch` method per
  [`ACQUISITION.md`](ACQUISITION.md). Start from `providers/localfile.py`. Put it
  in the git-ignored `providers/private.py`.
- **Add a legal provider.** A publisher OA API, a preprint server, an
  institutional proxy you're entitled to — same small class, inserted into
  `default_providers`.
- **Add a guideline source.** Copy the RCH crawler in `guidelines.py`; write the
  index-parse + body-extract for ASCIA / NICE / a state pathway; end in
  `library.store_text`.
- **Wire the citation graph** (designed, not built — see `ARCHITECTURE.md`):
  OpenAlex `referenced_works`/`cited_by` → a directed graph for snowball discovery
  and authority ranking.
- **Build the CKO condensation layer:** cluster the passage index into topic
  basins; distil each into canonical claims with a `determination` tag
  (stable-core vs underdetermined-granular); surface contradictions.
- **Add a MedCPT reranker** over the fused top-k passages for sharper retrieval.
- **Replace `data/question_bank.yaml`** with your own domains so `load` warms the
  topics you actually work in.

## Hygiene the agent should keep

- **Never commit the corpus or state.** `data/library/`, `data/passages/`,
  `ledger/`, `projects/` are git-ignored — keep them that way.
- **Never commit a private acquisition provider.** `providers/private.py` is
  git-ignored.
- **Serve stays private.** `serve` binds to `127.0.0.1`; reach the PWA over a LAN
  or tailnet, never the open internet. There is no auth — do not expose it.
- **Serialise writers (for now).** There is no single-writer lock yet, so don't
  run `load`/`ask` while `serve` is writing. (Building that lock is on the
  roadmap — a good agent task.)
