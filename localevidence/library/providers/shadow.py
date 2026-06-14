"""The shadow-library provider — a documented seam, intentionally unimplemented.

WHAT THIS IS
------------
The author's personal instance of this tool keeps a last-resort acquisition tier
that resolves a DOI on a shadow library (Anna's Archive / LibGen / Sci-Hub) when
no open-access copy exists. That tier is **not included in this repository** and
this class does not fetch anything — `fetch()` raises NotImplementedError, so the
default cascade is open-access only and entirely legal.

It is left here as a *seam*: a fully specified place to plug in your own
full-text provider. If you want acquisition beyond open access, you implement
this one method. The rest of the system — discovery, triage, the title-match
content guard, cataloguing, the passage index, the ledger — is already built
around it.

THE CONTRACT (what a working provider must do)
----------------------------------------------
A provider is just a `source` tag, three boolean flags, and one method::

    def fetch(self, doi, *, title="", pmid="", authors="", year="", journal="")
        -> bytes | None

Return the bytes of a PDF for `doi`, or None if you can't supply one. You do
NOT need to verify the file is the right paper — the cascade calls
`pdf_matches_title` on whatever you return and rejects a mismatch. That is why a
shadow source MUST set ``collision_prone = True``: shadow DOI→file resolution can
return an unrelated document, and the cascade will refuse to store a candidate
it cannot title-verify.

Conceptually a shadow provider does three things, none of which are shipped here:
  1. Resolve the DOI to one or more content identifiers on a shadow library.
  2. Download the bytes for an identifier (respecting whatever access method and
     credentials that library uses).
  3. Return the bytes; return None on any failure so the cascade reports
     ``not_found`` cleanly.

See ``docs/ACQUISITION.md`` for the full description, the reasons each guard
exists, and notes on doing this responsibly. Implementing it — and whether to —
is your decision, in your jurisdiction, for your own personal use.

LEGAL / ETHICAL NOTE
--------------------
Shipping working shadow-library code in a public repository is what gets repos
taken down, so it isn't here. The legal open-access providers (Unpaywall, Europe
PMC, local-file drop) cover a large fraction of the literature on their own. Use
those first; they are what the defaults give you.
"""

from __future__ import annotations

from typing import Optional


class ShadowProvider:
    """Last-resort acquisition tier — interface only; not implemented.

    Present in the default cascade (unless ``oa_only``) so the wiring is
    visible, but every call raises NotImplementedError and the cascade skips it.
    Implement `fetch` to enable it. See this module's docstring and
    docs/ACQUISITION.md.
    """

    source = "shadow"
    legal = False
    collision_prone = True

    def fetch(self, doi: str, *, title: str = "", pmid: str = "",
              authors: str = "", year: str = "", journal: str = "") -> Optional[bytes]:
        raise NotImplementedError(
            "The shadow-library acquisition tier is not included in this repository. "
            "Implement ShadowProvider.fetch to return PDF bytes for a DOI; see "
            "docs/ACQUISITION.md. Until then the cascade is open-access only.")
