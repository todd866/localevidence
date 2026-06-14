# Example knowledge pack

`mnd-pack/` is a real LocalEvidence knowledge pack — a shareable map of a motor
neurone disease / ALS literature corpus (~1,600 papers, 40 topic clusters: ALS
models, epidemiology, genetics, biomarkers, diagnostic criteria, bulbar/dysphagia,
…). It's the kind of corpus a clinician accumulates building out a topic.

It demonstrates the `pack` feature on real data, and it's meant to **grow**: the
paper list and the topic map are complete; the per-paper summaries start empty and
fill in over time (your own words — the Claude-in-the-loop step). Nothing
copyrighted is here — no full text, no PDFs, no verbatim passages — only
bibliographic facts and derived structure.

Rebuild the corpus locally from it (acquires each DOI under your own access):

```bash
python3 -m localevidence pack harvest examples/mnd-pack
```

See [`../docs/PACK.md`](../docs/PACK.md).
