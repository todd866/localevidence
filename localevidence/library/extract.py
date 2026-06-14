"""PDF text extraction + the title-match content guard.

`pdf_matches_title` is the single most important safety check in acquisition:
any provider — legal OA or a bring-your-own shadow tier — can occasionally hand
back the *wrong* PDF for a DOI. The cascade verifies every candidate's text
against the expected title before it is stored, so a wrong file is rejected
rather than silently catalogued. This is what makes a pluggable acquisition
backend safe: the verification lives here, not in the provider.

Extraction tries `pdftotext` (poppler) then PyMuPDF (`fitz`). OCR of scanned,
image-only PDFs is intentionally out of scope here (it needs tesseract and can
run for a long time); add it in your own fork if you acquire a lot of old scans.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path


def _toks(s: str) -> set[str]:
    return set(re.findall(r"[a-z]{4,}", (s or "").lower()))


def _is_thin(text: str, pdf: Path) -> bool:
    """Heuristic: text layer too sparse for the page count -> scanned image.

    Counts *unique* word tokens, not raw length, so a per-page watermark that
    repeats on every page doesn't masquerade as real content.
    """
    try:
        import fitz
        pages = len(fitz.open(str(pdf)))
    except Exception:
        pages = 1
    uniq = len(set(re.findall(r"[a-z]{4,}", (text or "").lower())))
    return uniq < max(50, 40 * pages)


def extract_text(pdf: Path, out: Path) -> bool:
    """Extract `pdf` to the text file `out`. Returns True if there's real text."""
    text = ""
    try:
        r = subprocess.run(["pdftotext", "-q", str(pdf), "-"],
                           capture_output=True, text=True, timeout=120)
        text = r.stdout
    except Exception:
        pass
    if _is_thin(text, pdf):
        try:
            import fitz
            text = "\n".join(p.get_text() for p in fitz.open(str(pdf)))
        except Exception:
            pass
    out.write_text(text)
    return out.stat().st_size > 50


def pdf_matches_title(pdf_bytes: bytes, title: str, min_ratio: float = 0.45) -> tuple[bool, float]:
    """True if the PDF's first-page text contains enough of `title`.

    Returns (ok, ratio). With no title to check against, passes — which is why
    the cascade refuses to auto-accept an *unverifiable* candidate from a
    collision-prone provider (see providers.pull).
    """
    if not title:
        return True, 1.0
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(pdf_bytes)
        tf.flush()
        tfname = tf.name
    head = ""
    try:
        import fitz
        doc = fitz.open(tfname)
        head = "".join(doc[i].get_text() for i in range(min(2, len(doc))))
    except Exception:
        pass
    finally:
        try:
            os.unlink(tfname)
        except Exception:
            pass

    tt = _toks(title)
    if not tt:
        return True, 1.0
    ratio = len(tt & _toks(head)) / len(tt)
    return ratio >= min_ratio, ratio
