"""Discovery: clinical question -> candidate literature with abstracts.

Free, broad, no downloads. Queries OpenAlex (huge, open, abstracts via the
inverted index) and optionally PubMed/E-utilities. Returns a deduped candidate
list rich enough for evidence-tier triage (type, cited_by, year, journal, pmid).

This is the recall layer. Nothing here fetches a PDF — that only happens for
the handful of candidates that survive triage.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from typing import Iterable, Optional

import requests

from . import config


OPENALEX = "https://api.openalex.org/works"

# OpenAlex `search` rejects several punctuation chars (?, comma, etc.) with a
# 400. Keep letters/digits/spaces/hyphens; collapse whitespace.
_SEARCH_CLEAN = re.compile(r"[^A-Za-z0-9 \-]+")


def _sanitize_search(s: str) -> str:
    return re.sub(r"\s+", " ", _SEARCH_CLEAN.sub(" ", s or "")).strip()


@dataclass
class Candidate:
    doi: str = ""
    pmid: str = ""
    openalex_id: str = ""
    title: str = ""
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    year: Optional[int] = None
    journal: str = ""
    type: str = ""
    cited_by: int = 0
    is_oa: bool = False
    found_via: list[str] = field(default_factory=list)   # source/query provenance
    # filled in by triage:
    tier: str = ""
    relevance: float = 0.0
    score: float = 0.0
    in_library: bool = False
    library_slug: str = ""

    @property
    def key(self) -> str:
        """Dedup key: prefer DOI, then PMID, then OpenAlex id."""
        return config.norm_doi(self.doi) or (f"pmid:{self.pmid}" if self.pmid else self.openalex_id)

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Candidate":
        return Candidate(**d)


def _abstract_from_inverted_index(idx: Optional[dict]) -> str:
    if not idx:
        return ""
    positions: list[tuple[int, str]] = []
    for word, places in idx.items():
        for p in places:
            positions.append((p, word))
    positions.sort()
    return " ".join(w for _, w in positions)


def _pmid_from_ids(ids: dict) -> str:
    pm = (ids or {}).get("pmid") or ""
    # e.g. "https://pubmed.ncbi.nlm.nih.gov/12345678"
    digits = "".join(ch for ch in pm.rsplit("/", 1)[-1] if ch.isdigit())
    return digits


def _parse_work(work: dict, via: str) -> Optional[Candidate]:
    doi = config.norm_doi(work.get("doi"))
    oa_id = (work.get("id") or "").rsplit("/", 1)[-1]
    title = work.get("title") or work.get("display_name") or ""
    if not title:
        return None

    authors = []
    for a in work.get("authorships", []) or []:
        name = (a.get("author") or {}).get("display_name")
        if name:
            authors.append(name)

    primary = work.get("primary_location") or {}
    src = (primary.get("source") or {})
    journal = src.get("display_name") or ""

    oa = work.get("open_access") or {}

    return Candidate(
        doi=doi,
        pmid=_pmid_from_ids(work.get("ids") or {}),
        openalex_id=oa_id,
        title=title,
        abstract=_abstract_from_inverted_index(work.get("abstract_inverted_index")),
        authors=authors,
        year=work.get("publication_year"),
        journal=journal,
        type=work.get("type") or "",
        cited_by=int(work.get("cited_by_count") or 0),
        is_oa=bool(oa.get("is_oa")),
        found_via=[via],
    )


# Fields requested from OpenAlex (keeps the response small + fast).
_SELECT = ",".join([
    "id", "doi", "ids", "title", "display_name", "publication_year",
    "type", "cited_by_count", "authorships", "primary_location",
    "open_access", "abstract_inverted_index",
])


def _openalex_query(
    search: str,
    *,
    per_page: int = 50,
    max_results: int = 120,
    from_year: Optional[int] = None,
    session: Optional[requests.Session] = None,
    verbose: bool = True,
) -> list[Candidate]:
    """Page-based query that PRESERVES OpenAlex relevance ranking.

    Cursor pagination forces a stable non-relevance sort, which buries the
    on-topic papers under high-citation word-matchers. Basic `page` paging
    keeps `relevance_score:desc`, so the candidate set is actually about the
    question. (Basic paging caps at page*per_page <= 10000, far beyond our N.)
    """
    s = session or requests.Session()
    out: list[Candidate] = []
    search = _sanitize_search(search)
    if not search:
        return out
    filters = ["has_abstract:true"]
    if from_year:
        filters.append(f"from_publication_date:{from_year}-01-01")
    page = 1
    while len(out) < max_results:
        params = {
            "search": search,
            "filter": ",".join(filters),
            "sort": "relevance_score:desc",
            "per_page": min(per_page, max_results - len(out)),
            "select": _SELECT,
            "page": page,
            "mailto": config.CONTACT_EMAIL,
        }
        try:
            r = s.get(OPENALEX, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            if verbose:
                print(f"  OpenAlex query failed ({search!r}): {e}")
            break
        results = data.get("results", []) or []
        if not results:
            break
        for rank, w in enumerate(results):
            c = _parse_work(w, via=f"openalex:{search}")
            if c:
                out.append(c)
        page += 1
        time.sleep(0.15)
    return out


def discover(
    question: str,
    *,
    extra_queries: Optional[Iterable[str]] = None,
    max_per_query: int = 120,
    from_year: Optional[int] = None,
    verbose: bool = True,
) -> list[Candidate]:
    """Run discovery for a clinical question and return deduped candidates.

    Queries: the full question, plus any caller-supplied focused queries
    (e.g. drug/condition phrasings). Dedup merges provenance so we can see
    which query surfaced a paper.
    """
    session = requests.Session()
    session.headers["User-Agent"] = f"LocalEvidence (mailto:{config.CONTACT_EMAIL})"

    queries: list[str] = [question.strip()]
    for q in (extra_queries or []):
        q = (q or "").strip()
        if q and q not in queries:
            queries.append(q)

    merged: dict[str, Candidate] = {}
    for q in queries:
        if verbose:
            print(f"  discover: OpenAlex <- {q!r}")
        for c in _openalex_query(
            q, max_results=max_per_query, from_year=from_year,
            session=session, verbose=verbose,
        ):
            k = c.key
            if not k:
                continue
            if k in merged:
                # merge provenance; keep the richer record
                merged[k].found_via.extend(v for v in c.found_via
                                           if v not in merged[k].found_via)
                if not merged[k].abstract and c.abstract:
                    merged[k].abstract = c.abstract
            else:
                merged[k] = c

    candidates = list(merged.values())
    if verbose:
        print(f"  discover: {len(candidates)} unique candidates "
              f"from {len(queries)} quer{'y' if len(queries) == 1 else 'ies'}")
    return candidates
