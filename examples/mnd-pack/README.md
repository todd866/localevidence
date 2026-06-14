# LocalEvidence knowledge pack

1634 papers · 40 topic clusters · built 2026-06-14

A shareable map of a literature corpus — **not the corpus itself**.

- `papers.jsonl` — the paper list (bibliographic metadata; DOIs to harvest).
- `summaries.jsonl` — what each paper provides (generated summaries, own words).
- `map.json` — topic clusters + a nearest-neighbour similarity graph.

No full text, PDFs, verbatim passages, or raw vectors are included — those stay with whoever holds the corpus.

## Rebuild the corpus from this pack

```
localevidence pack harvest <this-dir>
```

Harvests each paper by DOI under *your own* access and indexes it, reconstructing the corpus locally. What you can then ground in is yours.
