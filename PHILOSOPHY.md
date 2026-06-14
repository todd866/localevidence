# LocalEvidence — Philosophy

## What this is

A personal, compounding, open clinical-evidence engine. Not OpenEvidence —
*Local*Evidence: built around the topics you actually work in, on a corpus you
own, with reasoning you can audit, driven by successive versions of Claude Code
(or any capable agent). A mass-market product serves everyone the same way and
cannot know you. This system is shaped by your question stream and gets better
the more you use it — because each question grows the corpus the next one draws on.

## The mechanism: condensation

The medical literature is a high-dimensional object. Useful clinical knowledge
is a low-dimensional, coherent projection of it. LocalEvidence is **deliberate
dimensional collapse toward clinical utility** — a pipeline of condensation
steps, each shedding dimensions while preserving the grounded, load-bearing core:

```
whole papers  →  passages  →  claims  →  condensed cluster objects  →  an answer
   (raw)         (chunks)     (atomic)      (coded knowledge)          (the projection)
high-D ────────────────────────────────────────────────────────────────────► low-D
```

We use *dimensionality* in the ML/complex-systems sense: the effective degrees
of freedom of the coherently accessible content — not page count. Measurement is
dimensional collapse; here the collapse is performed on purpose, and the thing
we keep is the coherent manifold of clinical claims, not the bulk of the prose.

## Why it descends like gradient descent

Across many papers on one topic, redundant evidence **reinforces** the same
stable claims — these are the attractor basins of the knowledge manifold.
Contradictions, edge cases, and genuine novelty are the **residual** — the
gradient that still needs reading. Condensing a cluster of papers into its stable
claim-set *is* the descent; what the condensation cannot absorb is exactly what
is still uncertain and worth a human's attention. The corpus, the indices, and
the answer ledger are the accumulating "weights": each loading pass lowers the
loss on your topic space.

Its failure modes are the predicted ones — over-compression losing a
safety-critical caveat; a spurious basin from a biased corpus — which is why the
condensation layer is built to *not* collapse the genuinely underdetermined (see
[`ARCHITECTURE.md`](ARCHITECTURE.md), "Do not over-condense the granular layer").

## Three things compound — don't re-derive

LocalEvidence is built so a result computed once is reused, not recomputed, at
three levels:

1. **Papers** — every paper acquired is filed, deduped, and embedded once,
   forever (the local library). It ships empty; it grows as you ask.
2. **Structure** — embeddings, a persistent passage index, and (planned)
   citation/claim graphs and condensed cluster objects are built incrementally
   and reused.
3. **Knowledge** — every question, the evidence it used, the answer, and the
   *reasoning that produced it* are stored and grounded, so a similar future
   question reuses or refreshes the worked result instead of re-deriving it.

Layer 3 is the part a closed, one-size-fits-all product cannot replicate: it does
not — cannot — remember *your* reasoning on *your* questions.

## Loading: get ready before the question comes

The system is made "ready" by self-play on **simulated questions** across your
domains. Running the loop on a plausible question bank pre-acquires the corpus,
pre-builds the structure, and pre-condenses the topic space — so when a real
burning question arrives at the end of a hospital day, the answer is fast,
grounded, and already half-known. Loading is to LocalEvidence what training is to
a model: it pays the cost up front, in your topics, on your schedule.

## The compute asymmetry

A personal tool can spend far more compute per question than a mass-market
product can afford to spend per user. You can throw a lavish token budget and a
slow, thorough acquisition pass at a single question overnight; a product serving
millions cannot. That asymmetry — not a secret algorithm — is the structural
edge. Bad first-pass retrieval can be ploughed through with enough compute and a
corpus that keeps growing.

## Boundaries

A personal reference aid for a clinician's own use, not a validated medical
device or an autonomous decision-maker. Every claim is grounded to a retrievable
passage; provenance and reasoning are recorded, not hidden. Acquisition ships
with **legal, open-access providers only**; any provider beyond that is one you
add yourself, for your own use, in your own jurisdiction (see
[`docs/ACQUISITION.md`](docs/ACQUISITION.md)). The system's job is to put the
right grounded evidence in front of a clinician faster and more completely than a
closed product — and to be honest about what it could not find.
