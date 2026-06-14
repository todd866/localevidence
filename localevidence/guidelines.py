"""Guideline harvester — pull web-published clinical guidelines into the library.

Guidelines (e.g. RCH Melbourne CPGs, ASCIA, state pathways) are web pages without
DOIs, so the DOI-centric `ask` pipeline can't reach them — yet they are often the
convention-setters a clinician actually follows. This crawls a guideline source's
index, fetches each guideline, extracts the body text, and catalogues it into the
local library with a synthetic slug (source 'guideline:rch') so the persistent
passage index picks it up and every future question can ground in them.

The shipped source is RCH (a worked example of the pattern); adding ASCIA, NICE,
state pathways, etc. is a matter of writing another crawler that ends in
`library.store_text`.

Idempotent (skips guidelines already held unless --refresh) and politely paced.
Copyright stays the publisher's: harvested text lands in your personal corpus,
never shared.
"""

from __future__ import annotations

import html as _html
import re
import time
from typing import Optional

import requests

from . import config
from . import library  # self-contained local library (subpackage)


_UA = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "en-AU,en;q=0.9",
}

RCH_INDEX = "https://www.rch.org.au/clinicalguide/guideline_index/"
RCH_BASE = "https://www.rch.org.au"

# Index entries that are not clinical guidelines.
_RCH_SKIP = {
    "Parent_resources", "Retrieval_services", "CPG_Committee_Calendar",
    "CPG_feedback", "Nursing_Guidelines", "Paediatric_Improvement_Collaborative",
    "Paediatric_palliative_care_guidelines", "About_the_clinical_practice_guidelines",
    "guideline_index", "Search", "Resources",
}


def _clean_html(raw: str) -> str:
    """Crude but serviceable HTML -> readable text.

    Drops script/style/nav/header/footer, unescapes entities, collapses
    whitespace. Repeated chrome that survives is dropped downstream by the
    passage index's low-value-chunk filter; the goal here is to keep the
    guideline body intact, not to be a perfect reader.
    """
    h = re.sub(r"<script.*?</script>|<style.*?</style>|<!--.*?-->", " ", raw, flags=re.S | re.I)
    h = re.sub(r"<(nav|header|footer|aside)\b.*?</\1>", " ", h, flags=re.S | re.I)
    # Prefer the main content region if present.
    m = re.search(r"<main\b[^>]*>(.*?)</main>", h, flags=re.S | re.I)
    if m and len(m.group(1)) > 800:
        h = m.group(1)
    h = re.sub(r"<[^>]+>", " ", h)
    h = _html.unescape(h)
    h = re.sub(r"[ \t]+", " ", h)
    h = re.sub(r"\s*\n\s*", "\n", h)
    return re.sub(r"\n{2,}", "\n", h).strip()


def crawl_rch_index(session: requests.Session) -> list[tuple[str, str, str]]:
    """Return (name, title, url) for every RCH clinical practice guideline."""
    r = session.get(RCH_INDEX, timeout=30)
    r.raise_for_status()
    out: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for m in re.finditer(
        r"href=['\"](/clinicalguide/guideline_index/([A-Za-z][^/'\"#?]+)/?)['\"][^>]*>([^<]+)</a>",
        r.text,
    ):
        path, name, title = m.group(1), m.group(2), _html.unescape(m.group(3)).strip()
        if name in _RCH_SKIP or name in seen:
            continue
        seen.add(name)
        out.append((name, title, RCH_BASE + path))
    return out


def _store_text(slug: str, title: str, text: str, *, source: str,
                journal: str, url: str = "") -> None:
    """Catalogue a web guideline into the library (text file + catalog row)."""
    library.store_text(slug, title, text, source=source, journal=journal, url=url)


def rch_slug(name: str) -> str:
    return "rch-" + re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def harvest_rch(*, limit: int = 0, pace_s: float = 0.7, refresh: bool = False,
                min_chars: int = 500, verbose: bool = True) -> dict:
    """Crawl + fetch + catalogue the RCH CPG set. Returns a summary."""
    s = requests.Session()
    s.headers.update(_UA)
    guidelines = crawl_rch_index(s)
    if verbose:
        print(f"  RCH index: {len(guidelines)} guidelines")
    if limit:
        guidelines = guidelines[:limit]

    con = library.connect()
    existing = {row[0] for row in
                con.execute("SELECT slug FROM papers WHERE source='guideline:rch'").fetchall()}
    con.close()

    added = skipped = failed = thin = 0
    new_slugs: list[str] = []
    for i, (name, title, url) in enumerate(guidelines, 1):
        slug = rch_slug(name)
        if slug in existing and not refresh:
            skipped += 1
            continue
        try:
            r = s.get(url, timeout=30)
            if r.status_code != 200:
                failed += 1
                continue
            text = _clean_html(r.text)
            if len(text) < min_chars:
                thin += 1
                continue
            _store_text(slug, title, text, source="guideline:rch",
                        journal="RCH Clinical Practice Guidelines", url=url)
            added += 1
            new_slugs.append(slug)
            if verbose:
                print(f"  [{i}/{len(guidelines)}] + {slug}  ({len(text)} chars)  {title[:48]}")
        except requests.RequestException:
            failed += 1
        time.sleep(pace_s)

    summary = {"total": len(guidelines), "added": added, "skipped_existing": skipped,
               "failed": failed, "thin": thin, "new_slugs": new_slugs}
    if verbose:
        print(f"  harvest: +{added} added, {skipped} already held, "
              f"{failed} failed, {thin} too-thin")
    return summary


def index_guidelines(source: str = "guideline:rch", verbose: bool = True) -> int:
    """Index any not-yet-indexed guidelines into the persistent passage store, so
    every future question retrieves over them (the store searches the whole
    corpus). Returns passages added."""
    from .acquire import AcquiredPaper
    from .index import PassageIndex

    con = library.connect()
    rows = con.execute(
        "SELECT slug,title,year,journal,text_path FROM papers "
        "WHERE source=? AND text_path!=''", (source,)).fetchall()
    con.close()

    papers = [AcquiredPaper(slug=s, title=t, year=str(y or ""), journal=j,
                            text_path=tp, tier="guideline", relevance=0.0,
                            status="guideline", source=source)
              for (s, t, y, j, tp) in rows]
    pidx = PassageIndex()
    added = pidx.add_papers(papers, verbose=verbose)
    if verbose:
        print(f"  indexed {added} guideline passages "
              f"(store now {pidx.stats()['passages']} passages / {pidx.stats()['papers']} papers)")
    return added
