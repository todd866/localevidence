# Answer Style

LocalEvidence answers should feel like a fast clinical evidence consult, not a
general essay.

The target vibe:

- direct
- source-dense
- clinically practical
- conservative about uncertainty
- explicit about missing context
- easy to scan under time pressure

This is format mimicry, not copying any proprietary answer text.

## Default Shape

```text
Short answer
  2-4 sentences. Say the likely answer and the main branch point.

What changes the answer
  Missing context or patient factors that would materially alter management.

Evidence
  Bullet points tied to sources. Prefer guidelines, labels, systematic reviews,
  then trials/observational data.

Practical checks
  What to verify before acting: dose constraints, renal/hepatic function,
  pregnancy, allergies, interactions, severity, local protocol.

Follow-up questions
  2-3 high-yield questions that would naturally extend the evidence project.

Sources
  Reproducible source list.
```

## Voice Rules

- Start with the answer, not background.
- Prefer "use X unless Y" or "treat as X until Y is excluded" when evidence
  supports a branch.
- Keep paragraphs short.
- Use bullets for branches and caveats.
- Do not bury clinical action under pathophysiology.
- Do not overstate certainty where source coverage is weak.
- Name the missing data that blocks a safer answer.
- Distinguish source-backed statements from clinical judgement.
- When useful, end with generated follow-up questions that reveal the next
  evidence branch instead of generic "ask your doctor" language.

## Evidence Ordering

Rank sources by practical authority:

1. Local hospital protocol or state health pathway.
2. Australian national guideline / PBS / TGA product information.
3. International society guideline.
4. Systematic review or meta-analysis.
5. RCT or large cohort.
6. Review article / textbook / teaching source.
7. Case report or expert opinion.

When lower-level evidence is all that exists, say so.

For medication-selection questions, include a drug-label/formulary source layer
when possible. Prefer TGA product information or local formulary material for
Australian projects; use FDA/DailyMed only as a fallback or comparator source.

## Citation Density

Every management-changing claim should point to a source. For early versions,
that can be a plain source bullet rather than formal inline citations.

Good:

```text
Diazepam is the usual first-line benzodiazepine for uncomplicated alcohol
withdrawal; lorazepam/oxazepam become more attractive when severe liver disease
or oversedation risk makes diazepam accumulation unsafe. [Australian alcohol
treatment guideline; WA Health pathway]
```

Bad:

```text
Benzodiazepines are often used for alcohol withdrawal.
```

## Missing Context Pattern

Use a short "I need..." list when context changes safety:

```text
I would not make this dose-specific without:
- eGFR/creatinine trend
- hepatic impairment severity
- current sedatives/opioids
- pregnancy status
- allergy history
- local protocol
```

## Safety Language

Avoid presenting LocalEvidence as the final clinical authority.

Use:

- "This supports..."
- "I would check..."
- "This is enough for a first-pass answer, but..."
- "For a real case, local protocol/toxicology/ID advice matters because..."

Avoid:

- "You should always..."
- "This proves..."
- "No need to..."
- "Definitively..."
