"""Local file drop — the simplest acquisition provider, and a worked example.

Drop a PDF into the library's ``inbox/`` directory named after the paper's DOI
slug (e.g. ``10-1056-nejmoa2118542.pdf``) and this provider hands it to the
cascade, which title-verifies and files it like any other source. Useful when
you already hold a PDF (institutional access, a colleague, a publisher's own
open PDF you downloaded by hand) and just want it in the corpus.

It is also the minimal reference implementation of `AcquisitionProvider`: a
provider is just a `source` tag, three boolean flags, and a `fetch(doi, ...)`
that returns PDF bytes or None. A shadow-library provider has exactly this shape
— it just gets its bytes from somewhere else (see docs/ACQUISITION.md).
"""

from __future__ import annotations

from typing import Optional

from ..catalog import INBOX, slugify


class LocalFileProvider:
    source = "localfile"
    legal = True
    collision_prone = False

    def fetch(self, doi: str, *, title: str = "", pmid: str = "",
              authors: str = "", year: str = "", journal: str = "") -> Optional[bytes]:
        for name in self._candidates(doi, pmid):
            fp = INBOX / name
            if fp.exists():
                data = fp.read_bytes()
                if data[:5] == b"%PDF-":
                    return data
        return None

    @staticmethod
    def _candidates(doi: str, pmid: str) -> list[str]:
        names: list[str] = []
        if doi:
            names.append(f"{slugify(doi=doi)}.pdf")
        if pmid:
            names.append(f"pmid-{pmid}.pdf")
        return names
