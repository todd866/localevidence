from localevidence.index import Passage
from localevidence import verify


class FakeIndex:
    """Stands in for a warm PassageIndex. search() returns canned Passages."""
    def __init__(self, passages, papers=12, n_passages=300):
        self._passages, self._papers, self._n = passages, papers, n_passages

    def search(self, query, *, k=8, **kw):
        return self._passages[:k]

    def stats(self):
        return {"papers": self._papers, "passages": self._n}


def _p(slug, title, text, score, doi="", chunk_idx=0, tier="", year="2020"):
    return Passage(passage_id=0, slug=slug, text=text, title=title, doi=doi,
                   tier=tier, chunk_idx=chunk_idx, score=score, year=year)


def test_build_query_joins_text_context_topics():
    q = verify.build_query({"text": "ceftriaxone 50 mg/kg",
                            "context": "paediatric meningitis",
                            "topics": ["meningitis", "ceftriaxone"]})
    assert "ceftriaxone 50 mg/kg" in q and "meningitis" in q


def test_confidence_normalises_top_fused_score():
    # rank-0 in both lists ≈ 2/60 = 0.0333 -> ~1.0
    assert verify.confidence([_p("a", "A", "t", 2.0 / 60)]) == 1.0
    assert verify.confidence([]) == 0.0
    assert 0.0 <= verify.confidence([_p("a", "A", "t", 1.0 / 60)]) <= 1.0


def test_verify_evidence_core_shape():
    idx = FakeIndex([_p("s1", "Paper One", "ceftriaxone dosing in meningitis", 2.0 / 60,
                        doi="10.1/x", chunk_idx=3)])
    out = verify.verify_evidence({"text": "ceftriaxone 50 mg/kg", "topics": ["meningitis"]},
                                 index=idx)
    assert out["passages"][0]["id"] == "s1#3"
    assert out["passages"][0]["doi"] == "10.1/x"
    assert out["confidence"] == 1.0
    assert out["corpus_version"] == "le-12-300"
    assert out["acquired"]["ran"] is False
    assert out["citation_check"]["status"] == "n/a"


def test_citation_check_found_by_doi():
    ps = [_p("s1", "Paper One", "txt", 1.0 / 60, doi="10.1/AbC")]
    out = verify.citation_check({"doi": "10.1/abc"}, ps, index=None)
    assert out["status"] == "found" and out["matched_doi"] == "10.1/abc"


def test_citation_check_found_by_title_overlap():
    ps = [_p("s1", "Bacterial meningitis in children: management", "txt", 1.0 / 60)]
    out = verify.citation_check(
        {"title": "Management of bacterial meningitis in children"}, ps, index=None)
    assert out["status"] == "found"


def test_citation_check_absent_when_not_retrieved():
    ps = [_p("s1", "Unrelated asthma paper", "txt", 1.0 / 60, doi="10.9/zzz")]
    out = verify.citation_check({"doi": "10.1/abc"}, ps, index=None)
    assert out["status"] == "absent"


def test_acquire_on_miss_runs_when_low_confidence_and_important():
    calls = {"n": 0}

    class GrowIndex(FakeIndex):
        def search(self, query, *, k=8, **kw):
            # weak before acquire, strong after
            return [_p("s1", "A", "t", (2.0 / 60) if calls["n"] else (0.2 / 60))]

    idx = GrowIndex([])

    def acquirer(topic):
        calls["n"] += 1
        return {"pulled": 2, "topic": topic}

    out = verify.verify_evidence({"text": "rare claim", "topics": ["x"]}, index=idx,
                                 acquire_on_miss=True, importance=3, min_confidence=0.5,
                                 acquirer=acquirer)
    assert calls["n"] == 1
    assert out["acquired"] == {"ran": True, "pulled": 2, "topic": "x"}
    assert out["confidence"] == 1.0


def test_acquire_skipped_for_low_importance():
    idx = FakeIndex([_p("s1", "A", "t", 0.1 / 60)])
    out = verify.verify_evidence({"text": "c", "topics": ["x"]}, index=idx,
                                 acquire_on_miss=True, importance=1,
                                 acquirer=lambda t: {"pulled": 9})
    assert out["acquired"]["ran"] is False
