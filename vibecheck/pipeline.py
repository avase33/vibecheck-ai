"""The end-to-end feedback pipeline (ingest half).

One :class:`FeedbackPipeline` wires the per-ticket stages together and is shared
by the ingestion worker, the API and the CLI:

    noise filter → cache-backed enrichment → embedding → persist

Clustering is intentionally *not* done here — it runs in the nightly analytics
batch (:mod:`vibecheck.services.analytics`) over the accumulated tickets, exactly
like Spark/Ray daily jobs, so ingestion stays cheap and the topic model can be
rebuilt without touching the write path. The pipeline is synchronous and pure so
it can be unit-tested and benchmarked without any broker, DB server or model
download.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .config import Settings
from .core.cache import EnrichmentCache, build_cache
from .core.embeddings import Embedder, build_embedder
from .core.enrichment import Enricher, build_enricher
from .core.models import EnrichedTicket, Ticket
from .core.noise import classify
from .logging_setup import get_logger
from .storage.store import Store

log = get_logger("pipeline")


@dataclass
class IngestResult:
    ticket_id: str
    accepted: bool
    noise_reason: str = ""
    cache_hit_before: int = 0


class FeedbackPipeline:
    def __init__(self, settings: Optional[Settings] = None, store: Optional[Store] = None,
                 embedder: Optional[Embedder] = None, enricher: Optional[Enricher] = None,
                 cache: Optional[EnrichmentCache] = None) -> None:
        self.settings = settings or Settings()
        self.store = store or Store(self.settings.database_url)
        self.embedder = embedder or build_embedder(
            self.settings.embedding_backend, self.settings.embedding_dim, self.settings.embedding_model)
        self.enricher = enricher or build_enricher(self.settings.enricher_backend, self.settings.anthropic_model)
        self.cache = cache or build_cache(
            "redis" if self.settings.queue_backend == "celery" else "memory",
            self.settings.redis_url, self.settings.cache_enabled)

    def ingest(self, ticket: Ticket) -> IngestResult:
        verdict = classify(ticket.text)
        if verdict.is_noise:
            self.store.save_noise(ticket, verdict.reason)
            log.debug("dropped noise ticket %s (%s)", ticket.id, verdict.reason)
            return IngestResult(ticket.id, accepted=False, noise_reason=verdict.reason)

        hits_before = self.cache.stats.hits
        enrichment = self.cache.get_or_compute(ticket.text, self.enricher.enrich)
        embedding = self.embedder.embed(ticket.text)
        et = EnrichedTicket(ticket=ticket, enrichment=enrichment, embedding=embedding)
        self.store.save_enriched(et)
        return IngestResult(ticket.id, accepted=True,
                            cache_hit_before=self.cache.stats.hits - hits_before)

    def ingest_text(self, text: str, **kw) -> IngestResult:
        return self.ingest(Ticket(text=text, **kw))

    def close(self) -> None:
        self.store.close()
