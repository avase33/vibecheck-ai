"""Central configuration resolved from the environment.

Offline-first defaults: an in-memory queue, a deterministic mock enricher, and
hashing embeddings — so the whole platform runs with no external services. Point
the adapters at Redis/Celery, Anthropic, sentence-transformers and Qdrant for
production via environment variables.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class Settings:
    environment: str = "development"
    log_level: str = "INFO"

    # Queue: memory | celery
    queue_backend: str = "memory"
    redis_url: str = "redis://localhost:6379/0"

    # Enricher: mock | anthropic
    enricher_backend: str = "mock"
    anthropic_model: str = "claude-3-5-sonnet-latest"

    # Embeddings: hashing | sentence-transformers
    embedding_backend: str = "hashing"
    embedding_dim: int = 256
    embedding_model: str = "all-MiniLM-L6-v2"

    # Vector store: memory | qdrant
    vector_backend: str = "memory"
    qdrant_url: str = "http://localhost:6333"

    # Clustering
    cluster_similarity: float = 0.55   # cosine threshold to join a cluster
    min_cluster_size: int = 3
    emerging_window_hours: int = 24

    # Storage / cache
    database_url: str = "vibecheck.db"
    cache_enabled: bool = True

    # Alert routing
    alert_severity_threshold: int = 4   # 0..5
    slack_webhook: str = ""
    jira_url: str = ""

    @classmethod
    def from_env(cls) -> "Settings":
        g = os.environ.get
        enricher = g("VIBECHECK_ENRICHER") or ("anthropic" if g("ANTHROPIC_API_KEY") else "mock")
        return cls(
            environment=g("VIBECHECK_ENV", "development"),
            log_level=g("VIBECHECK_LOG_LEVEL", "INFO"),
            queue_backend=g("VIBECHECK_QUEUE", "memory"),
            redis_url=g("REDIS_URL", "redis://localhost:6379/0"),
            enricher_backend=enricher,
            embedding_backend=g("VIBECHECK_EMBEDDINGS", "hashing"),
            embedding_dim=int(g("VIBECHECK_EMBED_DIM", "256")),
            vector_backend=g("VIBECHECK_VECTOR", "memory"),
            qdrant_url=g("QDRANT_URL", "http://localhost:6333"),
            cluster_similarity=float(g("VIBECHECK_CLUSTER_SIM", "0.55")),
            min_cluster_size=int(g("VIBECHECK_MIN_CLUSTER", "3")),
            database_url=g("VIBECHECK_DB", "vibecheck.db"),
            cache_enabled=g("VIBECHECK_CACHE", "true").lower() in ("1", "true", "yes"),
            alert_severity_threshold=int(g("VIBECHECK_ALERT_SEV", "4")),
            slack_webhook=g("SLACK_WEBHOOK", ""),
            jira_url=g("JIRA_URL", ""),
        )
