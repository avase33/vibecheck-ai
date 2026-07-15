"""Text embeddings.

Default backend is a deterministic **hashing embedder** (the "hashing trick"):
each token is hashed into a fixed-width vector with a signed count, optionally
including bigrams and sublinear tf weighting, then L2-normalised. It needs no
model download and no network, so cosine similarity, clustering and the whole
pipeline run identically on any machine and in CI.

Set ``VIBECHECK_EMBEDDINGS=sentence-transformers`` to swap in real
``sentence-transformers`` vectors via :class:`SentenceTransformerEmbedder`.
"""

from __future__ import annotations

import hashlib
import math
from typing import Iterable, Protocol, Sequence

from .tokenizer import bigrams, tokenize


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]: ...


def _h(token: str, seed: int = 0) -> int:
    return int.from_bytes(hashlib.md5(f"{seed}:{token}".encode()).digest()[:8], "big")


class HashingEmbedder:
    """Signed hashing-trick embedder with sublinear tf and L2 normalisation."""

    def __init__(self, dim: int = 256, use_bigrams: bool = True) -> None:
        self.dim = dim
        self.use_bigrams = use_bigrams

    def _features(self, text: str) -> list[str]:
        toks = tokenize(text)
        if self.use_bigrams:
            toks = toks + bigrams(toks)
        return toks

    def embed(self, text: str) -> list[float]:
        counts: dict[int, float] = {}
        for tok in self._features(text):
            hsh = _h(tok)
            counts[hsh] = counts.get(hsh, 0.0) + 1.0
        vec = [0.0] * self.dim
        for hsh, c in counts.items():
            weight = 1.0 + math.log(c)          # sublinear tf
            sign = 1.0 if (hsh >> 63) & 1 else -1.0  # signed hashing removes bias
            vec[hsh % self.dim] += sign * weight
        return _l2(vec)

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class SentenceTransformerEmbedder:
    """Real neural embeddings (optional dependency)."""

    def __init__(self, model: str = "all-MiniLM-L6-v2") -> None:
        from sentence_transformers import SentenceTransformer  # type: ignore

        self._model = SentenceTransformer(model)
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, text: str) -> list[float]:
        return _l2(list(map(float, self._model.encode(text))))

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        vecs = self._model.encode(list(texts))
        return [_l2(list(map(float, v))) for v in vecs]


def build_embedder(backend: str = "hashing", dim: int = 256, model: str = "all-MiniLM-L6-v2") -> Embedder:
    if backend == "sentence-transformers":
        return SentenceTransformerEmbedder(model)
    return HashingEmbedder(dim=dim)


# ---- vector math ---------------------------------------------------------

def _l2(vec: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0.0:
        return vec
    return [x / norm for x in vec]


def cosine(a: Sequence[float], b: Sequence[float]) -> float:
    # inputs are L2-normalised, so cosine == dot product
    return sum(x * y for x, y in zip(a, b))


def centroid(vectors: Iterable[Sequence[float]]) -> list[float]:
    vecs = list(vectors)
    if not vecs:
        return []
    dim = len(vecs[0])
    acc = [0.0] * dim
    for v in vecs:
        for i, x in enumerate(v):
            acc[i] += x
    acc = [x / len(vecs) for x in acc]
    return _l2(acc)
