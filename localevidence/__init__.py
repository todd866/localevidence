"""LocalEvidence retrieval pipeline.

An on-demand clinical-evidence engine: discover candidate literature, triage by
relevance and evidence tier, acquire full text into a local library (which warms
over time), index at passage level, and assemble a grounded evidence pack a
clinician (or Claude) can synthesise from.

Self-contained. The local library (`localevidence.library`) owns:
  - pull()        -> the pluggable acquisition cascade (legal OA by default;
                     a you-supply-it shadow tier for everything else),
  - the catalog + PDF/text store, DOI/title verification, and chunking.
sentence-transformers MiniLM provides the embeddings.

Stages live in their own modules and each writes a JSON checkpoint so an `ask`
run is resumable:
    discovery -> triage -> acquire -> index -> evidence pack
"""

__all__ = ["config", "discovery", "triage", "acquire", "index", "evidence", "pipeline"]
