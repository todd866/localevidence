# OpenEvidence calibration — response shape

Calibrating against OpenEvidence (OE) is useful because its response shape is a
*product*: A/B-tuned on millions of clinician sessions. Reverse-engineering it
lets LocalEvidence inherit that tuning, then exceed it with the things a
mass-market black box structurally can't do. This is format/shape mimicry, never
copying OE answer text — raw OE captures stay in a project's `private/`; only the
structural analysis is recorded.

## OE's standard shape (reverse-engineered)

1. **Lead paragraph** — the direct answer with the key *quantitative anchors* up
   front (doses, the headline effect size), densely cited inline `[1-2]`.
2. **Hierarchical body** — bold section headers → sub-sections → one fact per
   bullet. Every fact that *can* carry a number does (dose, %, OR, 95% CI,
   Z-score), each with an inline numbered citation.
3. **Localization section** — a dedicated *"Practice Variation in <country>"* or
   *"<country> Epidemiology Context"* block: local cohort data + practice notes.
4. **Figure** — embedded where a key paper has one (licensed).
5. **Follow-up question** — "Would you like to explore …".
6. **Reference list** — numbered; each entry = Title · Journal · Year · Authors ·
   **evidence-type tag** (Guideline / SR / RCT / Review / Observational / Recent).

Stylistic signature: headline-first; dense numbered citations (ranges); maximal
quantitative specificity; evidence-grade visible at a glance via the type tags.

## What OE's shape omits — LocalEvidence's edges

OE answers do **not** include, and LE should always keep:

- **What changes the answer** — the branch points / patient factors.
- **Practical checks before acting** — what to verify (dose, renal/hepatic, age).
- **Honest gaps** — "RCH does not state X"; the residual the corpus can't ground.
- **Determination status** — stable-core (assert the number) vs
  underdetermined-granular (give the range + "your guideline picks X"); never
  force-collapse a free-parameter threshold.
- **Per-claim auditability** — every claim ties to a retrievable passage; OE's
  retrieval is a black box.

## The calibrated LocalEvidence shape (the target)

**OE's structure + LE's honesty edges:**

```
Short answer            headline + key numbers, up front, cited
What changes it         branch points / patient factors           (LE edge)
Management / evidence    bold sections → bullet-per-fact, numbers + citations
                         (lead with the local guideline where it speaks)
Local / AU practice      the convention-setter section (RCH/ASCIA) + variation
Practical checks         what to verify before acting               (LE edge)
Gaps / uncertainty       what the corpus could not ground; determination status (LE edge)
Follow-up questions      2–3 high-yield next branches
Sources                  numbered; each TAGGED with evidence type + year
```

### Citation + reference conventions (adopt from OE)

- **Numbered inline citations** `[1]`, `[1-2]` after each management-changing claim.
- **Evidence-type-tagged references**: every source carries `[Guideline]`,
  `[Systematic review]`, `[RCT]`, `[Cohort/Observational]`, `[Review]`, plus year.
  RCH/ASCIA web guidelines are `[Guideline — RCH/ASCIA]` (no DOI).
- **Quantitative density**: state the number wherever a grounded one exists; if
  the corpus only gives a range or can't ground it, say so (don't invent precision).

## Using OE as an acquisition target

A calibration run also yields an **acquisition list**: the specific papers OE
cited that LE's corpus lacks (e.g. the Australian cohort epidemiology). Resolve
them to DOIs and `library.pull` them — closing the first-ask recall gap the
on-demand corpus has. OE's citations are, usefully, a curated reading list.
