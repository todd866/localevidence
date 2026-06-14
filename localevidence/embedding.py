"""One shared MiniLM load for the whole pipeline.

Triage embeds abstracts; the index embeds passages; the ledger embeds questions.
All want the same model and the same vector space. Loading the model once and
returning L2-normalized float32 (so cosine == dot product) keeps the rest of the
code to plain numpy.
"""

from __future__ import annotations

from typing import Sequence

import numpy as np

from . import config

_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(config.EMBED_MODEL)
    return _MODEL


def embed(texts: Sequence[str], *, batch_size: int = 64, show_progress: bool = False) -> np.ndarray:
    """Return an (N, dim) float32 array of L2-normalized embeddings."""
    text_list = [t if t else " " for t in texts]
    if not text_list:
        return np.zeros((0, 384), dtype="float32")
    model = get_model()
    vecs = model.encode(
        text_list,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )
    return np.asarray(vecs, dtype="float32")


def cosine(query_vec: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Cosine similarities of one normalized query vector against rows of a
    normalized matrix. With normalized inputs this is just a dot product."""
    if matrix.size == 0:
        return np.zeros((0,), dtype="float32")
    return matrix @ query_vec
