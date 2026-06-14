from localevidence.index import PassageIndex
from localevidence.library import catalog
from localevidence.ingest import index_library


def test_index_library_filters_and_is_incremental(tmp_path):
    src = "ingesttest"
    for slug, title in [("m1", "Amyotrophic lateral sclerosis diagnosis"),
                        ("m2", "Motor neurone disease and its mimics"),
                        ("p1", "Croup management in children")]:
        f = tmp_path / f"{slug}.txt"
        f.write_text(f"{title}. " * 80)
        catalog.upsert(dict(slug=slug, doi=f"10.5/{slug}", title=title, tier="",
                            source=src, text_path=str(f), pdf_path="", pmid="",
                            year="2020", journal="J"))
    # a catalog row whose text file is missing -> skipped
    catalog.upsert(dict(slug="gone", doi="10.5/gone", title="Amyotrophic ghost",
                        source=src, text_path=str(tmp_path / "nope.txt"),
                        pdf_path="", pmid="", year="", journal=""))

    idx = PassageIndex(store_dir=tmp_path / "store")
    summ = index_library(source=src, match=r"amyotrophic|motor neuron",
                         index=idx, verbose=False)
    assert summ["considered"] == 2                       # m1, m2 (p1 off-topic, gone missing)
    assert summ["passages_added"] > 0
    assert "m1" in idx.indexed_slugs and "m2" in idx.indexed_slugs
    assert "p1" not in idx.indexed_slugs and "gone" not in idx.indexed_slugs

    # incremental: re-running indexes nothing new
    again = index_library(source=src, match=r"amyotrophic|motor neuron",
                          index=idx, verbose=False)
    assert again["passages_added"] == 0
