"""Word-level overlapping text chunking — the unit the passage index stores."""

from __future__ import annotations

from typing import List


def chunk_text(
    text: str,
    target_words: int = 200,
    overlap_words: int = 50,
    min_chunk_words: int = 20,
) -> List[str]:
    """Split text into overlapping word-level chunks.

    Each chunk starts ``step = target - overlap`` words after the previous one,
    giving consistent coverage. Returns ``[text]`` if shorter than
    *target_words*, or ``[]`` if empty.
    """
    words = text.split()
    if not words:
        return []
    if len(words) <= target_words:
        return [" ".join(words)]

    chunks: List[str] = []
    step = max(target_words - overlap_words, 1)
    start = 0
    while start < len(words):
        end = min(start + target_words, len(words))
        chunk = " ".join(words[start:end])
        if len(chunk.split()) >= min_chunk_words:
            chunks.append(chunk)
        if end == len(words):
            break
        start += step
    return chunks
