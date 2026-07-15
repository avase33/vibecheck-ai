"""Vector index abstraction.

Default is an exact in-memory index (fine for demos and CI). ``QdrantVectorIndex``
is a drop-in adapter for production similarity search at scale. Both expose the
same ``add`` / ``search`` surface so the pipeline is storage-agnostic.
"""

from __future__ import annotations

from typing import Protocol, Sequence

from .embeddings import cosine


class VectorIndex(Protocol):
    def add(self, id: str, vector: Sequence[float]) -> None: ...

    def search(self, vector: Sequence[float], k: int = 5) -> list[tuple[str, float]]: ...


class InMemoryVectorIndex:
    def __init__(self) -> None:
        self._items: dict[str, list[float]] = {}

    def add(self, id: str, vector: Sequence[float]) -> None:
        self._items[id] = list(vector)

    def search(self, vector: Sequence[float], k: int = 5) -> list[tuple[str, float]]:
        scored = [(i, cosine(vector, v)) for i, v in self._items.items()]
        scored.sort(key=lambda p: p[1], reverse=True)
        return scored[:k]

    def __len__(self) -> int:
        return len(self._items)


class QdrantVectorIndex:  # pragma: no cover - requires qdrant
    def __init__(self, url: str, collection: str = "vibecheck", dim: int = 256) -> None:
        from qdrant_client import QdrantClient  # type: ignore
        from qdrant_client.models import Distance, VectorParams  # type: ignore

        self._client = QdrantClient(url=url)
        self._collection = collection
        try:
            self._client.get_collection(collection)
        except Exception:
            self._client.create_collection(
                collection_name=collection,
                vectors_config=VectorParams(size=dim, distance=Distance.COSINE),
            )
        self._n = 0

    def add(self, id: str, vector: Sequence[float]) -> None:
        from qdrant_client.models import PointStruct  # type: ignore

        self._n += 1
        self._client.upsert(self._collection,
                            points=[PointStruct(id=self._n, vector=list(vector), payload={"ref": id})])

    def search(self, vector: Sequence[float], k: int = 5) -> list[tuple[str, float]]:
        res = self._client.search(self._collection, query_vector=list(vector), limit=k)
        return [(p.payload["ref"], float(p.score)) for p in res]


def build_index(backend: str = "memory", url: str = "", dim: int = 256) -> VectorIndex:
    if backend == "qdrant" and url:
        return QdrantVectorIndex(url, dim=dim)
    return InMemoryVectorIndex()
