from localevidence import eval as ev


def _grd(coverage, hall):
    return {"grounding": {"coverage": coverage, "hallucinated_citations": hall}}


def test_summarize():
    s = ev.summarize([_grd(1.0, 0), _grd(0.5, 2), _grd(0.0, 1)])
    assert s["n"] == 3
    assert s["mean_coverage"] == 0.5
    assert s["mean_hallucinated"] == 1.0
    assert s["fully_grounded"] == 1
    assert s["any_hallucination"] == 2


def test_lift_isolates_harness_contribution():
    harness_runs = [_grd(0.9, 0), _grd(1.0, 0)]   # well grounded, no hallucinations
    baseline_runs = [_grd(0.5, 1), _grd(0.6, 2)]  # weaker, hallucinating
    out = ev.lift(harness_runs, baseline_runs)
    assert out["coverage_gain"] == round(0.95 - 0.55, 3)
    assert out["hallucination_reduction"] == round(1.5 - 0.0, 3)


def test_run_eval_with_mock(monkeypatch):
    from localevidence import harness, inference
    monkeypatch.setattr(inference, "generate",
                        lambda *a, **k: "Grounded claim [s1#0].")
    passages = [{"id": "s1#0", "paper": "P", "doi": "10/x", "text": "t"}]
    out = ev.run_eval(["Q1?", "Q2?"], retrieve=lambda q, kk: passages,
                      model="ollama:x", baseline=True)
    assert len(out["rows"]) == 2
    assert out["summary"]["n"] == 2
    assert "lift" in out
    assert out["rows"][0]["harness"]["valid"] == ["s1#0"]
