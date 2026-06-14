from localevidence.library import catalog


def test_store_text_and_stats():
    rec = catalog.store_text("rch-croup", "Croup",
                             "Croup: dexamethasone 0.15 mg/kg oral.",
                             source="guideline:rch", journal="RCH CPG")
    assert rec["slug"] == "rch-croup"
    assert rec["text_path"].endswith("rch-croup.txt")
    assert catalog.stats()["papers"] >= 1


def test_find_dedup_by_doi_case_insensitive():
    txt = catalog.TEXTS / "10-x-y.txt"
    txt.write_text("hello world")
    catalog.upsert(dict(slug="10-x-y", doi="10.x/y", text_path=str(txt),
                        pdf_path="", title="T", source="test"))
    rec = catalog.find(doi="https://doi.org/10.X/Y")   # normalised + case-folded
    assert rec is not None and rec["slug"] == "10-x-y"


def test_find_missing_returns_none():
    assert catalog.find(doi="10.0/definitely-not-here") is None


def test_find_stale_pdf_without_text_is_dropped():
    catalog.upsert(dict(slug="stale", doi="10.s/t", pdf_path="/no/such/file.pdf",
                        text_path="", title="S", source="test"))
    assert catalog.find(doi="10.s/t") is None   # claims a PDF that's gone, no text
