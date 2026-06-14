"""Unpaywall — legal open-access full text.

Unpaywall (https://unpaywall.org) indexes the open-access copy of a DOI when one
exists: gold OA at the publisher, or a green-OA author manuscript / repository
deposit. Free; asks only for a contact email. Best for MDPI/BMC/PMC and any
paper with a legitimate OA location.
"""

from __future__ import annotations

import sys
from typing import Optional

import requests

from ... import config

_PLACEHOLDER_EMAIL = "you@example.com"
_warned = False


class UnpaywallProvider:
    source = "unpaywall"
    legal = True
    collision_prone = False

    def __init__(self, email: Optional[str] = None):
        self.email = email or config.CONTACT_EMAIL

    def fetch(self, doi: str, *, title: str = "", pmid: str = "",
              authors: str = "", year: str = "", journal: str = "") -> Optional[bytes]:
        # Unpaywall rejects an empty or placeholder email with HTTP 422, which
        # would otherwise be swallowed and look like "no OA copy exists". Make
        # the misconfiguration loud (once) and skip rather than fail silently.
        if not self.email or self.email == _PLACEHOLDER_EMAIL:
            global _warned
            if not _warned:
                _warned = True
                print("  [acquire] Unpaywall needs a real contact email — set "
                      "LOCALEVIDENCE_EMAIL to your own address (the placeholder is "
                      "rejected). Skipping Unpaywall.", file=sys.stderr)
            return None
        try:
            r = requests.get(f"https://api.unpaywall.org/v2/{doi}",
                             params={"email": self.email}, timeout=25)
            if r.status_code != 200:
                return None
            loc = (r.json() or {}).get("best_oa_location") or {}
            url = loc.get("url_for_pdf") or loc.get("url")
            if not url:
                return None
            p = requests.get(url, timeout=90)
            if p.status_code == 200 and p.content[:5] == b"%PDF-":
                return p.content
        except Exception:
            return None
        return None
