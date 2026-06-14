"""Europe PMC — legal open-access full text (the PMC mirror, ~5M+ free articles).

Catches green-OA copies Unpaywall misses: a paper can be subscription-only at
the publisher yet have a free author manuscript / PMC deposit that Europe PMC
serves. The reliable PDF is the article render
``.../articles/{PMCID}?pdf=render`` plus any PDF URLs the record advertises as
Free / Open access.
"""

from __future__ import annotations

from typing import Optional

import requests

from ... import config


class EuropePMCProvider:
    source = "europepmc"
    legal = True
    collision_prone = False

    def __init__(self, email: Optional[str] = None):
        self.email = email or config.CONTACT_EMAIL  # not required by EPMC; kept for parity

    def fetch(self, doi: str, *, title: str = "", pmid: str = "",
              authors: str = "", year: str = "", journal: str = "") -> Optional[bytes]:
        try:
            q = requests.get(
                "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
                params={"query": f'DOI:"{doi}"', "format": "json", "resultType": "core"},
                timeout=25)
            if q.status_code != 200:
                return None
            results = ((q.json() or {}).get("resultList") or {}).get("result") or []
            if not results:
                return None
            rec = results[0]
            urls: list[str] = []
            for u in ((rec.get("fullTextUrlList") or {}).get("fullTextUrl") or []):
                if (u.get("documentStyle") == "pdf"
                        and u.get("availability") in ("Free", "Open access")
                        and u.get("url")):
                    urls.append(u["url"])
            pmcid = rec.get("pmcid")
            if pmcid:
                urls.append(f"https://europepmc.org/articles/{pmcid}?pdf=render")
            seen: set[str] = set()
            for url in urls:
                if url in seen:
                    continue
                seen.add(url)
                try:
                    p = requests.get(url, timeout=90, allow_redirects=True)
                    if p.status_code == 200 and p.content[:5] == b"%PDF-":
                        return p.content
                except Exception:
                    continue
        except Exception:
            return None
        return None
