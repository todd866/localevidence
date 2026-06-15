from localevidence import governance as gov
from localevidence import inference
from localevidence import operating_point as op


def _op(**kw):
    base = dict(node="n", base_rate=0.05, cost_fn=10.0, cost_fp=1.0, escalate_threshold=0.9)
    base.update(kw)
    return op.OperatingPoint(**base)


def test_decision_log_records_and_is_attributable(tmp_path):
    log = gov.DecisionLog(tmp_path / "g.jsonl")
    o = _op(node="rural-gp", cost_fn=50.0, cost_fp=1.0)
    rec = gov.govern(o, 0.10, log=log, question="MRI for low-risk headache?",
                     task_class="test-ordering", tier="large", at="2026-06-15T00:00:00")
    assert rec["action"] == "investigate"
    rows = log.records()
    assert len(rows) == 1
    r = rows[0]
    assert r["node"] == "rural-gp" and r["task_class"] == "test-ordering"
    assert r["operating_point"]["cost_fp"] == 1.0 and r["at"] == "2026-06-15T00:00:00"


def test_investigate_rate_per_node(tmp_path):
    log = gov.DecisionLog(tmp_path / "g.jsonl")
    aggressive = _op(node="A", cost_fn=50.0, cost_fp=1.0)    # low threshold -> investigates
    for p in (0.10, 0.20, 0.30):
        gov.govern(aggressive, p, log=log, task_class="test-ordering", tier="large")
    cautious = _op(node="B", cost_fn=1.0, cost_fp=50.0)      # high threshold -> watches
    for p in (0.10, 0.20, 0.30):
        gov.govern(cautious, p, log=log, task_class="test-ordering", tier="large")
    # "wants to MRI everyone" is now a measurable, per-node rate
    assert log.investigate_rate("A") == 1.0
    assert log.investigate_rate("B") == 0.0
    s = log.summary("A")
    assert s["n"] == 3 and s["counts"]["investigate"] == 3


def test_governed_answer_gate_refuses_small_tier(tmp_path):
    log = gov.DecisionLog(tmp_path / "g.jsonl")
    gate_fn = lambda q, model=None: {"task_class": "test-ordering", "tier": "small", "allowed": False}
    out = gov.governed_answer("Should I MRI?", _op(), retrieve=lambda q, k: [], model="ollama:14b",
                              log=log, gate_fn=gate_fn, estimate_fn=lambda *a, **k: 0.1)
    assert out["disposition"] == "refused"
    assert log.records() == []          # nothing decided or logged when the gate refuses


def test_governed_answer_decides_and_dial_governs_the_action(tmp_path):
    log = gov.DecisionLog(tmp_path / "g.jsonl")
    gate_fn = lambda q, model=None: {"task_class": "test-ordering", "tier": "large", "allowed": True}
    aggressive = _op(node="tert", cost_fn=50.0, cost_fp=1.0)
    out = gov.governed_answer("Should I MRI?", aggressive, retrieve=lambda q, k: [], model="opus",
                              log=log, gate_fn=gate_fn, estimate_fn=lambda *a, **k: 0.10)
    assert out["disposition"] == "decided" and out["decision"]["action"] == "investigate"
    assert len(log.records()) == 1
    # SAME question + SAME estimate, only the dial changes -> the action moves
    cautious = op.OperatingPoint(node="tert", base_rate=0.05, cost_fn=50.0, cost_fp=50.0,
                                 escalate_threshold=0.9)
    out2 = gov.governed_answer("Should I MRI?", cautious, retrieve=lambda q, k: [], model="opus",
                               log=log, gate_fn=gate_fn, estimate_fn=lambda *a, **k: 0.10)
    assert out2["decision"]["action"] == "watch"


def test_estimate_probability_parses_and_falls_back(monkeypatch):
    monkeypatch.setattr(inference, "generate", lambda *a, **k: "The pre-test probability is 0.12.")
    assert gov.estimate_probability("q", retrieve=lambda q, k: [], model="x") == 0.12
    monkeypatch.setattr(inference, "generate", lambda *a, **k: "About 12%")
    assert gov.estimate_probability("q", retrieve=lambda q, k: [], model="x") == 0.12
    def boom(*a, **k):
        raise inference.InferenceError("down")
    monkeypatch.setattr(inference, "generate", boom)
    assert gov.estimate_probability("q", retrieve=lambda q, k: [], model="x") is None
