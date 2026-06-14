"""Acquisition providers + the cascade that runs them.

`pull(doi, ...)` walks an ordered list of providers. Each provider tries to
return the bytes of a PDF for the given DOI. The cascade verifies every
candidate against the expected title before storing it, so a provider that
returns the wrong file is rejected, not catalogued.

The shipped defaults are LEGAL, open-access providers (a local-file drop, then
Unpaywall, then Europe PMC). The last-resort tier — a *shadow library* provider
that resolves a DOI on Anna's Archive / LibGen / Sci-Hub — is intentionally
**not implemented** here. `ShadowProvider` is a documented stub that raises
``NotImplementedError`` so the cascade skips it. The interface it must satisfy
is fully specified in ``docs/ACQUISITION.md``; implement it yourself if you
choose to. Nothing in this repository fetches from a shadow library.

This is the whole point of the project's design: the architecture is the public
good; the corpus you grow and the acquisition tier you add are yours.
"""

from __future__ import annotations

import importlib
import os
from typing import Iterable, Optional, Protocol, Union, runtime_checkable

from .. import catalog
from ..catalog import find, norm_doi
from ..extract import pdf_matches_title

# Concrete providers (re-exported so `from .providers import ShadowProvider`
# works, and so users can build custom cascades from them).
from .localfile import LocalFileProvider
from .unpaywall import UnpaywallProvider
from .europepmc import EuropePMCProvider
from .shadow import ShadowProvider


@runtime_checkable
class AcquisitionProvider(Protocol):
    """A source of full-text PDFs for a DOI.

    Attributes
    ----------
    source : str
        Tag recorded in the catalog for papers this provider supplied.
    legal : bool
        True for open-access providers shipped here. A bring-your-own shadow
        provider sets this False; it changes nothing operationally, but it keeps
        the provenance of every stored paper honest in the catalog.
    collision_prone : bool
        True if this source can resolve a DOI to an unrelated file (shadow
        libraries do). When True, the cascade refuses to accept a candidate it
        cannot title-verify (i.e. when no expected title was supplied), rather
        than risk storing the wrong paper.
    """

    source: str
    legal: bool
    collision_prone: bool

    def fetch(self, doi: str, *, title: str = "", pmid: str = "",
              authors: str = "", year: str = "",
              journal: str = "") -> Union[bytes, Iterable[bytes], None]:
        """Return a PDF for `doi`, or None if this provider can't supply one.

        Return value may be:
          - ``bytes``           — a single candidate PDF (the common case);
          - an iterable/generator of ``bytes`` — several candidate PDFs to try
            in order (a collision-prone source resolves a DOI to several files;
            the cascade title-checks each and keeps the first that matches);
          - ``None``            — nothing available.

        You do NOT verify the file — the cascade title-checks whatever you yield.
        May raise ``NotImplementedError`` to signal "not configured" — the cascade
        catches that and moves on.
        """
        ...


# Status strings the rest of the pipeline understands (acquire.py keys on these).
#   already_have / pulled / no_oa / wrong_paper_only / not_found / no_doi

_warned_shadow = False


def _warn_shadow_once(prov) -> None:
    global _warned_shadow
    if not _warned_shadow:
        _warned_shadow = True
        print(f"  [acquire] shadow tier '{getattr(prov, 'source', 'shadow')}' is "
              f"present but not implemented — skipping it. See docs/ACQUISITION.md "
              f"to add your own full-text provider.")


def load_shadow_provider():
    """Resolve the last-resort provider, in priority order:

    1. ``LOCALEVIDENCE_SHADOW`` env, as ``module.path:ClassName`` — load it.
    2. A local, git-ignored ``localevidence/library/providers/private.py`` that
       exports ``Provider`` (or ``ShadowProvider``) — the dogfooding convention:
       drop your own implementation here and it is used automatically, without
       ever being committed.
    3. Otherwise the documented ``ShadowProvider`` stub (raises
       NotImplementedError, so the cascade stays open-access only).

    This is how the *public* repo runs as a daily driver: the code is shared; the
    private acquisition implementation and the corpus are not.
    """
    spec = os.environ.get("LOCALEVIDENCE_SHADOW")
    if spec:
        mod_name, _, cls_name = spec.partition(":")
        try:
            mod = importlib.import_module(mod_name)
            return getattr(mod, cls_name or "ShadowProvider")()
        except Exception as e:
            print(f"  [acquire] LOCALEVIDENCE_SHADOW={spec!r} failed to load "
                  f"({type(e).__name__}: {e}); using the stub.")
    try:
        from . import private as _private  # git-ignored; not shipped
        cls = getattr(_private, "Provider", None) or getattr(_private, "ShadowProvider")
        return cls()
    except Exception:
        return ShadowProvider()


def default_providers(*, oa_only: bool = False,
                      contact_email: Optional[str] = None) -> list:
    """The shipped cascade: local file drop -> Unpaywall -> Europe PMC.

    Appends the last-resort tier unless ``oa_only``. By default that tier is the
    unimplemented stub (so the cascade is open-access only and entirely legal);
    if you have supplied your own provider (see ``load_shadow_provider``) it is
    used instead.
    """
    email = contact_email
    provs: list = [LocalFileProvider(),
                   UnpaywallProvider(email), EuropePMCProvider(email)]
    if not oa_only:
        provs.append(load_shadow_provider())
    return provs


def pull(doi: str, *, title: str = "", pmid: str = "", cite_key: str = "",
         authors: str = "", year: str = "", journal: str = "",
         verify: bool = True, oa_only: bool = False,
         providers: Optional[list] = None,
         contact_email: Optional[str] = None) -> dict:
    """Acquire a paper into the library, verified against its title.

    Walks the provider cascade; stores the first candidate PDF that passes the
    title check. Idempotent: a paper already held returns immediately. Returns a
    dict carrying the catalog row plus a ``_status``.
    """
    doi = norm_doi(doi)
    hit = find(doi=doi, pmid=pmid)
    if hit:
        return {**hit, "_status": "already_have"}
    if not doi:
        return {"_status": "no_doi", "title": title}

    provs = providers if providers is not None else \
        default_providers(oa_only=oa_only, contact_email=contact_email)

    best_ratio = 0.0          # best title-match among rejected candidates
    saw_candidate = False
    errors: list[dict] = []   # provider failures, surfaced (not swallowed)

    def _candidates(out):
        """Normalise a provider's return to an iterable of candidate PDFs."""
        if out is None:
            return []
        if isinstance(out, (bytes, bytearray)):
            return [bytes(out)]
        return out  # an iterable / generator of byte-strings

    for prov in provs:
        try:
            out = prov.fetch(doi, title=title, pmid=pmid, authors=authors,
                             year=str(year or ""), journal=journal)
        except NotImplementedError:
            _warn_shadow_once(prov)
            continue
        except Exception as e:
            errors.append({"source": getattr(prov, "source", "?"),
                           "error": f"{type(e).__name__}: {e}"})
            continue

        try:
            for pdf in _candidates(out):
                if not pdf or pdf[:5] != b"%PDF-":
                    continue
                saw_candidate = True
                # A collision-prone provider with no title to check against is
                # unverifiable — refuse it rather than risk the wrong paper.
                if verify and not title and getattr(prov, "collision_prone", False):
                    continue
                ok, ratio = (True, 1.0) if not verify else pdf_matches_title(pdf, title)
                if ok:
                    rec = catalog.store_pdf(
                        pdf, doi=doi, pmid=pmid, title=title, authors=authors,
                        year=str(year or ""), journal=journal, cite_key=cite_key,
                        source=getattr(prov, "source", "unknown"))
                    return {**rec, "_status": "pulled"}
                best_ratio = max(best_ratio, ratio)
        except Exception as e:
            # A lazy generator can raise mid-iteration (e.g. a download failed).
            errors.append({"source": getattr(prov, "source", "?"),
                           "error": f"{type(e).__name__}: {e}"})

    result: dict = {"doi": doi, "title": title, "best_ratio": round(best_ratio, 2)}
    if errors:
        result["errors"] = errors          # distinguishes breakage from real absence
    if best_ratio > 0:
        result["_status"] = "wrong_paper_only"
    elif oa_only and not saw_candidate:
        result["_status"] = "no_oa"
    else:
        result["_status"] = "not_found"
    return result
