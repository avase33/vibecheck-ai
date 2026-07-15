"""Nightly analytics batch.

In production this runs on Spark/Ray; here it is a deterministic in-process job
with the same contract. It rebuilds cluster centroids incrementally from newly
ingested tickets, recomputes topic stats, flags emerging topics, and produces the
prioritised roadmap the dashboard renders.

The roadmap score blends *volume*, *severity*, *negative sentiment* and
*churn risk* so the top of the list is "what will hurt retention most", which is
exactly the ranking a product/eng team wants each morning.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from ..core.clustering import IncrementalClusterer
from ..core.models import Cluster
from ..logging_setup import get_logger
from ..storage.store import Store

log = get_logger("analytics")


@dataclass
class RoadmapItem:
    cluster: Cluster
    score: float
    rationale: str

    def to_dict(self) -> dict:
        d = self.cluster.to_dict()
        d["priority_score"] = round(self.score, 2)
        d["rationale"] = self.rationale
        return d


def roadmap_score(c: Cluster, max_size: int) -> tuple[float, str]:
    volume = (c.size / max_size) if max_size else 0.0            # 0..1
    severity = c.avg_severity / 5.0                              # 0..1
    negativity = max(0.0, -c.avg_sentiment)                      # 0..1
    churn = c.high_churn_share                                   # 0..1
    score = 100 * (0.35 * volume + 0.30 * severity + 0.20 * churn + 0.15 * negativity)
    if c.emerging:
        score *= 1.15  # spiking topics get a boost
    reasons = []
    if severity >= 0.6:
        reasons.append("high severity")
    if churn >= 0.25:
        reasons.append(f"{round(churn*100)}% churn-risk mentions")
    if volume >= 0.5:
        reasons.append(f"{c.size} reports")
    if c.emerging:
        reasons.append("emerging/spiking")
    if negativity >= 0.4:
        reasons.append("strongly negative sentiment")
    return score, ", ".join(reasons) or "steady volume"


class AnalyticsBatch:
    def __init__(self, store: Store, clusterer: Optional[IncrementalClusterer] = None,
                 similarity: float = 0.55, min_cluster_size: int = 3) -> None:
        self.store = store
        self.clusterer = clusterer or IncrementalClusterer(similarity, min_cluster_size)

    def rebuild(self, since: float = 0.0) -> list[Cluster]:
        """Re-cluster tickets ingested since ``since`` on top of existing centroids."""
        self.clusterer.load(self.store.load_clusters())
        new = self.store.iter_enriched(since=since)
        for et in new:
            self.clusterer.assign(et)
        clusters = self.clusterer.all_clusters()
        self.store.upsert_clusters(clusters)
        log.info("analytics rebuild: %d tickets, %d clusters", len(new), len(clusters))
        return self.clusterer.clusters

    def roadmap(self, limit: int = 15) -> list[RoadmapItem]:
        clusters = self.store.load_clusters()
        clusters = [c for c in clusters if c.size > 0]
        max_size = max((c.size for c in clusters), default=1)
        items = []
        for c in clusters:
            score, why = roadmap_score(c, max_size)
            items.append(RoadmapItem(cluster=c, score=score, rationale=why))
        items.sort(key=lambda it: it.score, reverse=True)
        return items[:limit]

    def emerging(self, window_hours: int = 24) -> list[Cluster]:
        cutoff = time.time() - window_hours * 3600
        return [c for c in self.store.load_clusters() if c.created_at >= cutoff and c.size > 0]
