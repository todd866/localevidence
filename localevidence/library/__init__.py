"""The local paper library: catalog + PDF/text store + acquisition cascade.

A self-contained replacement for the personal `PaperLibrary` the author runs.
The public surface the rest of LocalEvidence uses:

  - pull(doi, title=, ...)  -> acquire a paper (legal OA providers by default)
  - find(doi=/pmid=/md5=)   -> catalog lookup (dedup / already-have)
  - store_text(...)         -> catalogue a text-only doc (guidelines)
  - chunk_text(...)         -> passage chunking
  - TEXTS / PDFS / INBOX    -> on-disk store locations
  - stats()                 -> corpus size

Acquisition is pluggable (see `providers/`): legal open-access providers ship
and work out of the box; the shadow-library tier is a documented, unimplemented
seam (see docs/ACQUISITION.md).
"""

from __future__ import annotations

from .catalog import (
    LIBRARY_ROOT, PDFS, TEXTS, INBOX, DB,
    connect, _conn, find, upsert, store_pdf, store_text, import_pdf, stats,
    norm_doi, slugify,
)
from .extract import extract_text, pdf_matches_title
from .chunk import chunk_text
from .providers import (
    pull, default_providers, AcquisitionProvider, ShadowProvider,
)

__all__ = [
    "LIBRARY_ROOT", "PDFS", "TEXTS", "INBOX", "DB",
    "connect", "_conn", "find", "upsert", "store_pdf", "store_text",
    "import_pdf", "stats", "norm_doi", "slugify",
    "extract_text", "pdf_matches_title", "chunk_text",
    "pull", "default_providers", "AcquisitionProvider", "ShadowProvider",
]
