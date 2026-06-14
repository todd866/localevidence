# Acquisition — the provider cascade

This document specifies how LocalEvidence gets full text, how to add your own
provider, and exactly what the deliberately-unshipped "shadow" tier would have to
do. It is the **kernel**: enough structure that you (with Claude Code) can rebuild
what the author runs, without this repository shipping anything that fetches from
a shadow library.

## The model

`localevidence.library.pull(doi, title=, ...)` walks an **ordered list of
providers**. The cascade — not any individual provider — owns correctness:

```
for provider in cascade:
    pdf = provider.fetch(doi, title=...)        # may return bytes, None, or raise
    if pdf is a real PDF and it passes the TITLE CHECK:
        store it (catalog + extract text) → return "pulled"
# nothing passed → "not_found" / "wrong_paper_only" / "no_oa"
```

The single most important line is the **title check**
(`extract.pdf_matches_title`): the first page's text must contain enough of the
expected title. This is what makes a pluggable backend safe — a provider can hand
back the *wrong* paper for a DOI and the cascade rejects it instead of silently
cataloguing it. **Verification lives in the cascade, not in the provider**, so a
provider you write only has to fetch; it never has to be trusted to be correct.

## The provider interface

A provider is a tiny object — three attributes and one method:

```python
class MyProvider:
    source = "myprovider"     # tag recorded in the catalog for provenance
    legal = True              # honest flag; False for a shadow tier
    collision_prone = False   # True if this source can return the wrong file

    def fetch(self, doi, *, title="", pmid="", authors="", year="", journal=""):
        """Return one of:
             - bytes                 a single candidate PDF (the common case),
             - an iterable of bytes  several candidate PDFs to try in order,
             - None                  nothing available.
        Raise NotImplementedError to mean 'not configured' (the cascade skips it).
        You do NOT verify the file — the cascade title-checks whatever you yield,
        and keeps the first candidate that matches."""
        ...
```

Returning an **iterable** is what a collision-prone source needs: DOI→file
resolution is many-to-one and the first hit is often the wrong edition, so you
`yield` each candidate and let the cascade's title check pick the right one.

- `source` — recorded on every paper this provider supplies, so the catalog keeps
  honest provenance of where each PDF came from.
- `legal` — documentation only; it changes nothing operationally. Set it
  truthfully.
- `collision_prone` — **set this `True` for any shadow-library source.** Shadow
  DOI→file resolution can map a DOI to an unrelated document. When `True`, the
  cascade refuses to accept a candidate it *cannot* title-verify (i.e. when no
  expected title was supplied), rather than risk storing the wrong paper. Legal
  OA providers set it `False`.

The minimal worked example is
[`localevidence/library/providers/localfile.py`](../localevidence/library/providers/localfile.py):
~20 lines that read a PDF from an `inbox/` directory. Read it first — every
provider, including a shadow one, has exactly that shape.

## Shipped providers (legal, open-access)

| `source`     | what it does                                              |
|--------------|-----------------------------------------------------------|
| `localfile`  | reads `data/library/inbox/<doi-slug>.pdf` if you put one there |
| `unpaywall`  | the open-access copy of a DOI, via the Unpaywall API      |
| `europepmc`  | green-OA / PMC author manuscripts, via the Europe PMC API |

These run by default and cover a large fraction of the literature. The default
cascade is **open-access only** unless you add a tier below.

## The shadow tier — specified, not shipped

The author keeps a last-resort provider that resolves a DOI on a *shadow library*
(Anna's Archive / LibGen / Sci-Hub) when no OA copy exists. It is **not in this
repository**; `providers/shadow.py` is a stub that raises `NotImplementedError`.
If you choose to run acquisition that way, you implement one `fetch` method.

Conceptually, a shadow provider does three things — and nothing here does any of
them for you:

1. **Resolve** the DOI to one or more content identifiers on the shadow library
   (these services expose a lookup from DOI to a file hash / record id).
2. **Download** the bytes for an identifier, using whatever access method and
   credentials that service requires.
3. **Yield** the bytes — ideally *all* candidate identifiers' files in turn (as an
   iterable/generator), so the cascade title-checks each and keeps the right one;
   return `None` (or raise) on failure, which the cascade records as an error and
   reports as `not_found` rather than masking it. Set `collision_prone = True` and
   `legal = False`.

That is the entire specification. Steps 1–2 — the endpoints, the request shape, any
account/key handling, the rate-limiting — are **deliberately out of scope here**:
whether to implement them, and how, is your decision, in your jurisdiction, under
your own access terms and responsibility. They are left out on purpose: shipping
working shadow-library code in a public repository is what gets repositories taken
down, and it is not the novel or valuable part of this project. The interface above
is the legitimate architecture; the rest is a boundary, not a how-to.

## Supplying your own provider

Three mechanisms, in the order the cascade resolves them:

1. **Environment** — `LOCALEVIDENCE_SHADOW="mypkg.module:MyProvider"`. The cascade
   imports and instantiates it as the last tier.
2. **Git-ignored drop-in** (the dogfooding convention) — create
   `localevidence/library/providers/private.py` exporting a `Provider` class. It
   is `.gitignore`d, so your implementation is used automatically and is never
   committed while the code that calls it is.
3. **Custom cascade** — build the provider list yourself and pass it:
   ```python
   from localevidence.library.providers import pull, UnpaywallProvider
   pull(doi, title=t, providers=[UnpaywallProvider(), MyProvider()])
   ```

To add another **legal** provider (a publisher OA API, an institutional proxy you
are entitled to use, a preprint server), write the same small class and insert it
into `default_providers`. No shadow tier required to be useful.

## Responsibilities

Open-access acquisition is unambiguous — those copies are free to read by design.
Anything beyond it is your decision, governed by your jurisdiction, your
institution's access terms, and the publisher's copyright. Acquired text lands in
your personal corpus and is never shared by this tool. Decide deliberately.
