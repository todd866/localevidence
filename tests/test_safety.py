from localevidence import safety, inference

CAT = [
    {"id": "dka", "category": "acute-emergency", "tier": "critical",
     "triggers": ["dka", "diabetic ketoacidosis"],
     "rule": "No bolus unless shocked; correct slowly.",
     "violation_checks": ["recommends a fluid bolus when not shocked",
                          "recommends rapid glucose correction"]},
    {"id": "constipation", "category": "test-ordering", "tier": "high",
     "triggers": ["constipation"], "rule": "No AXR for functional constipation.",
     "violation_checks": ["orders an abdominal X-ray for functional constipation"]},
]


def test_match_rules_keyword_and_tier():
    r = safety.match_rules("Manage this child's DKA please", CAT, semantic=False)
    assert [x["id"] for x in r] == ["dka"]
    assert safety.tier_of(r) == "critical"
    assert safety.match_rules("how do I treat a sore throat", CAT, semantic=False) == []
    assert safety.tier_of([]) == "standard"


def test_match_rules_semantic_catches_paraphrase():
    # fake embedder: 'ketoacidosis'/'dka' -> axis 0, else axis 1 — so a paraphrase
    # with no literal trigger still matches the DKA rule's cue semantically.
    import numpy as np
    def fake_emb(texts):
        def vec(t):
            t = t.lower()
            if "ketoacid" in t or "dka" in t:
                return [1.0, 0.0, 0.0]
            if "constipation" in t or "axr" in t:
                return [0.0, 1.0, 0.0]
            return [0.0, 0.0, 1.0]
        return np.array([vec(t) for t in texts])
    # 'ketoacidosis' is NOT a literal trigger of CAT['dka'] (triggers: dka / diabetic ketoacidosis)
    q = "child with severe ketoacid crisis, what fluids"
    r = safety.match_rules(q, CAT, embedder=fake_emb, threshold=0.9)
    assert "dka" in [x["id"] for x in r]
    # an unrelated question matches nothing
    assert safety.match_rules("ankle sprain advice", CAT, embedder=fake_emb, threshold=0.9) == []


def test_rules_constraint_text_lists_rules():
    txt = safety.rules_constraint_text(CAT[:1])
    assert "HARD SAFETY RULES" in txt and "No bolus unless shocked" in txt


def test_safety_critic_flags_yes(monkeypatch):
    monkeypatch.setattr(inference, "generate", lambda *a, **k: "1: YES\n2: NO")
    v = safety.safety_critic("Q", "bolus 20 mL/kg now", CAT[:1], model="ollama:x")
    assert len(v) == 1 and v[0]["rule_id"] == "dka" and v[0]["violated"] is True
    assert "bolus" in v[0]["check"]


def test_safety_critic_unavailable_fails_safe(monkeypatch):
    def boom(*a, **k):
        raise inference.InferenceError("down")
    monkeypatch.setattr(inference, "generate", boom)
    v = safety.safety_critic("Q", "A", CAT[:1], model="ollama:x")
    assert v and v[0]["violated"] is None and v[0]["tier"] == "critical"


def _answer_fn_factory(text):
    def fn(question, *, retrieve, model=None, k=8, constraints=""):
        fn.seen_constraints = constraints
        return {"answer": text, "grounding": {"coverage": 0.0}, "stages": ["draft"]}
    return fn


def test_guarded_answer_served_when_clean(monkeypatch):
    monkeypatch.setattr(inference, "generate", lambda *a, **k: "1: NO\n2: NO")  # critic clears
    out = safety.guarded_answer("treat the DKA", retrieve=lambda q, k: [],
                                answer_fn=_answer_fn_factory("cautious fluids, slow correction"),
                                model="ollama:x", catalogue=CAT)
    assert out["disposition"] == "served" and out["violations"] == []
    assert out["rules_applied"] == ["dka"] and out["tier"] == "critical"


def test_guarded_answer_abstains_on_unresolved_critical(monkeypatch):
    # critic always flags check 1 (the critical bolus violation), even after revise
    monkeypatch.setattr(inference, "generate", lambda *a, **k: "1: YES\n2: NO")
    out = safety.guarded_answer("treat the DKA", retrieve=lambda q, k: [],
                                answer_fn=_answer_fn_factory("give a 20 mL/kg bolus"),
                                model="ollama:x", catalogue=CAT)
    assert out["disposition"] == "abstain"
    assert out["safety_note"] and "verify" in out["safety_note"].lower()


def test_guarded_answer_injects_constraints(monkeypatch):
    monkeypatch.setattr(inference, "generate", lambda *a, **k: "1: NO\n2: NO")
    fn = _answer_fn_factory("ok")
    safety.guarded_answer("a DKA case", retrieve=lambda q, k: [], answer_fn=fn,
                          model="ollama:x", catalogue=CAT)
    assert "HARD SAFETY RULES" in fn.seen_constraints  # rules were injected into the answer
