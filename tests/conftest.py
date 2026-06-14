"""Test fixtures.

Two things make the suite fast and hermetic:
  - the library is redirected to a temp dir BEFORE localevidence is imported, so
    no test touches a real corpus;
  - the embedding model is replaced by a deterministic hash-based fake, so tests
    never download MiniLM / import torch and never hit the network.
"""

import hashlib
import os
import tempfile

# Must happen before any `import localevidence.*` so config picks these up.
os.environ.setdefault("LOCALEVIDENCE_LIBRARY", tempfile.mkdtemp(prefix="le-test-lib-"))
os.environ.setdefault("LOCALEVIDENCE_EMAIL", "test.runner@example.org")

import numpy as np
import pytest

DIM = 384


def _fake_vec(text: str) -> np.ndarray:
    """Deterministic per-text unit vector (identical text -> identical vector)."""
    seed = int.from_bytes(hashlib.sha256((text or " ").encode()).digest()[:8], "little")
    v = np.random.default_rng(seed).standard_normal(DIM).astype("float32")
    return v / (np.linalg.norm(v) or 1.0)


@pytest.fixture(autouse=True)
def fake_embedder(monkeypatch):
    import localevidence.embedding as emb

    def fake_embed(texts, **_kw):
        texts = list(texts)
        if not texts:
            return np.zeros((0, DIM), dtype="float32")
        return np.stack([_fake_vec(t) for t in texts]).astype("float32")

    monkeypatch.setattr(emb, "embed", fake_embed)
    monkeypatch.setattr(emb, "get_model", lambda: object())
    yield
