"""High-level façade tying the pipeline, analytics and agent together.

`VibeCheck` is the one object the CLI, API and tests instantiate. It owns a
pipeline (ingest), an analytics batch (roadmap) and an alerting agent (routing),
sharing a single store so everything stays consistent.
"""

from __future__ import annotations

from typing import Iterable, Optional

from .config import Settings
from .core.models import Alert, Ticket
from .pipeline import FeedbackPipeline, IngestResult
from .services.agent import AlertingAgent
from .services.analytics import AnalyticsBatch, RoadmapItem
from .services.ingestion import IngestionWorker


class VibeCheck:
    def __init__(self, settings: Optional[Settings] = None,
                 pipeline: Optional[FeedbackPipeline] = None) -> None:
        self.settings = settings or Settings()
        self.pipeline = pipeline or FeedbackPipeline(self.settings)
        self.store = self.pipeline.store
        self.analytics = AnalyticsBatch(
            self.store, similarity=self.settings.cluster_similarity,
            min_cluster_size=self.settings.min_cluster_size)
        self.agent = AlertingAgent(self.settings.alert_severity_threshold)

    # ingest ---------------------------------------------------------------

    def ingest(self, ticket: Ticket) -> IngestResult:
        return self.pipeline.ingest(ticket)

    def ingest_many(self, tickets: Iterable[Ticket]) -> dict:
        accepted = noise = 0
        for t in tickets:
            r = self.pipeline.ingest(t)
            accepted += int(r.accepted)
            noise += int(not r.accepted)
        return {"accepted": accepted, "noise": noise}

    def worker(self) -> IngestionWorker:
        return IngestionWorker(self.pipeline)

    # analyze --------------------------------------------------------------

    def roadmap(self, limit: int = 15) -> list[RoadmapItem]:
        return self.analytics.roadmap(limit=limit)

    def run_alerts(self) -> list[Alert]:
        return self.agent.run_many(self.store.load_clusters(), store=self.store)

    def stats(self) -> dict:
        s = self.store.stats()
        s["cache"] = self.pipeline.cache.stats.to_dict()
        return s

    def close(self) -> None:
        self.pipeline.close()
