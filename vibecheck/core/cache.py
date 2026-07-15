"""LLM response cache.

Support feedback is highly repetitive ("app keeps crashing", "can't log in"),
so a normalised-content cache in front of the enricher turns most calls into
free lookups. The default backend is process-local; point ``REDIS_URL`` at Redis
for a shared cache across workers. Hit/miss stats back the README's
"~40% fewer API calls" benchmark.
"""

from __future__ import annotations

import hashlib
import re
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from .models import Enrichment
from .enrichment import validate_enrichment
import json


def cache_key(text: str) -> str:
    norm = re.sub(r"\s+", " ", (text or "").strip().lower())
    return hashlib.sha256(norm.encode()).hexdigest()


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return 0.0 if self.total == 0 else self.hits / self.total

    def to_dict(self) -> dict:
        return {"hits": self.hits, "misses": self.misses, "total": self.total,
                "hit_rate": round(self.hit_rate, 4)}


class InMemoryCache:
    def __init__(self) -> None:
        self._data: dict[str, str] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[str]:
        with self._lock:
            return self._data.get(key)

    def set(self, key: str, value: str) -> None:
        with self._lock:
            self._data[key] = value


class RedisCache:
    def __init__(self, url: str, prefix: str = "vibecheck:enrich:") -> None:
        import redis  # type: ignore

        self._r = redis.Redis.from_url(url)
        self._prefix = prefix

    def get(self, key: str) -> Optional[str]:
        v = self._r.get(self._prefix + key)
        return v.decode() if v else None

    def set(self, key: str, value: str) -> None:
        self._r.set(self._prefix + key, value)


class EnrichmentCache:
    """Caches enrichment results and tracks hit stats."""

    def __init__(self, backend=None, enabled: bool = True) -> None:
        self.backend = backend or InMemoryCache()
        self.enabled = enabled
        self.stats = CacheStats()

    def get_or_compute(self, text: str, compute: Callable[[str], Enrichment]) -> Enrichment:
        if not self.enabled:
            return compute(text)
        key = cache_key(text)
        cached = self.backend.get(key)
        if cached is not None:
            self.stats.hits += 1
            return validate_enrichment(cached)
        self.stats.misses += 1
        result = compute(text)
        self.backend.set(key, json.dumps(result.to_dict()))
        return result


def build_cache(backend_kind: str = "memory", redis_url: str = "", enabled: bool = True) -> EnrichmentCache:
    backend = RedisCache(redis_url) if backend_kind == "redis" and redis_url else InMemoryCache()
    return EnrichmentCache(backend=backend, enabled=enabled)
