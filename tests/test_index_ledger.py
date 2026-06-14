from localevidence.acquire import AcquiredPaper
from localevidence.index import PassageIndex
from localevidence.ledger import Ledger


def test_index_add_search_and_alignment(tmp_path):
    a = tmp_path / "a.txt"
    a.write_text("Diazepam is first-line for alcohol withdrawal in most patients. " * 60)
    b = tmp_path / "b.txt"
    b.write_text("Croup is treated with a single dose of dexamethasone. " * 60)
    idx = PassageIndex(store_dir=tmp_path / "store")
    n = idx.add_papers([
        AcquiredPaper(slug="a", title="A", text_path=str(a), tier="rct"),
        AcquiredPaper(slug="b", title="B", text_path=str(b), tier="review"),
    ], verbose=False)
    assert n > 0
    # dense matrix stays row-aligned with the catalog
    assert idx.vectors.shape[0] == len(idx.meta)
    # the lexical (BM25) arm finds paper a by its drug terms even though the
    # fake embedder gives random dense vectors
    res = idx.search("alcohol withdrawal diazepam", k=5)
    assert res and any(r.slug == "a" for r in res)


def test_index_incremental_skips_indexed_slug(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("word " * 300)
    idx = PassageIndex(store_dir=tmp_path / "s2")
    paper = AcquiredPaper(slug="a", title="A", text_path=str(f), tier="article")
    assert idx.add_papers([paper], verbose=False) > 0
    assert idx.add_papers([paper], verbose=False) == 0   # same slug -> no re-chunk


def test_ledger_record_update_roundtrip(tmp_path):
    led = Ledger(store_dir=tmp_path / "led")
    eid = led.record("What HR threshold admits anorexia nervosa?",
                     evidence=[{"slug": "x", "doi": "10.x/y"}])
    assert led.stats()["questions"] == 1
    assert led.update(eid, answer="Admit if HR<40.", confidence="high")
    e = led.get(eid)
    assert e["answer"] == "Admit if HR<40." and e["confidence"] == "high"
    assert led.stats()["answered"] == 1


def test_ledger_find_similar_excludes_identical(tmp_path):
    led = Ledger(store_dir=tmp_path / "led2")
    led.record("identical question text")
    # identical string is deliberately excluded (it surfaces *different* priors)
    assert led.find_similar("identical question text", threshold=0.99) == []
