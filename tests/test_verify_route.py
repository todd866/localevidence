from localevidence import server
from localevidence.index import Passage


def _p(slug, title, text, score, doi="", chunk_idx=0):
    return Passage(passage_id=0, slug=slug, text=text, title=title, doi=doi,
                   score=score, chunk_idx=chunk_idx, year="2020")


def test_handle_verify_payload(monkeypatch):
    idx = type("I", (), {"search": lambda self, q, k=8, **kw: [
                  _p("s1", "Paper", "ceftriaxone 50 mg/kg meningitis", 2.0 / 60, "10.1/x")],
                  "stats": lambda self: {"papers": 5, "passages": 50}})()
    monkeypatch.setattr(server, "_INDEX", idx)
    body = {"claim": {"text": "ceftriaxone 50 mg/kg", "topics": ["meningitis"]}}
    out = server.handle_verify(body)
    assert out["passages"][0]["id"] == "s1#0"
    assert out["corpus_version"] == "le-5-50"


def test_handle_verify_rejects_empty_claim(monkeypatch):
    monkeypatch.setattr(server, "_INDEX", object())
    out = server.handle_verify({"claim": {"text": "  "}})
    assert out.get("error")
