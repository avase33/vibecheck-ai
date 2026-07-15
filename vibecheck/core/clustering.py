"""Incremental, density-aware topic clustering.

Enterpret-style products need topics that *evolve*: an emerging bug should form a
new cluster the same night it appears, without retraining a global model over the
entire history. This module implements online single-pass clustering inspired by
HDBSCAN's density idea but streaming-friendly:

* Each incoming vector joins the nearest existing cluster if cosine similarity to
  its centroid exceeds ``similarity_threshold``; otherwise it seeds a *provisional*
  cluster.
* Provisional clusters that reach ``min_cluster_size`` are promoted to real topics
  (this is the density/min-samples filter — sparse singletons never become noise
  topics).
* Centroids are updated incrementally (running mean), so a nightly batch only
  needs the *new* tickets, not a full re-fit.
* Clusters formed within ``emerging_window`` are flagged ``emerging`` for the
  roadmap "what's new / spiking" view.

Everything is pure Python and deterministic, so clustering results are stable in
tests and CI. A ``QdrantVectorIndex`` adapter can back the nearest-centroid
search at scale, but the default in-memory index is exact.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional, Sequence

from .embeddings import cosine
from .models import Cluster, EnrichedTicket, new_id


@dataclass
class _Live:
    """Mutable working state for a cluster during streaming."""

    cluster: Cluster
    sum_vec: list[float]
    severities: list[int] = field(default_factory=list)
    sentiments: list[float] = field(default_factory=list)
    churns: list[str] = field(default_factory=list)
    areas: Counter = field(default_factory=Counter)
    provisional: bool = True

    def recompute_centroid(self) -> None:
        n = len(self.cluster.member_ids)
        if n == 0:
            return
        mean = [x / n for x in self.sum_vec]
        norm = sum(v * v for v in mean) ** 0.5
        self.cluster.centroid = [v / norm for v in mean] if norm else mean

    def refresh_stats(self) -> None:
        c = self.cluster
        if self.severities:
            c.avg_severity = sum(self.severities) / len(self.severities)
        if self.sentiments:
            c.avg_sentiment = sum(self.sentiments) / len(self.sentiments)
        if self.churns:
            c.high_churn_share = self.churns.count("high") / len(self.churns)
        if self.areas:
            c.dominant_feature_area = self.areas.most_common(1)[0][0]
            c.label = _label(c.dominant_feature_area, self.areas)
        c.updated_at = time.time()


def _label(area: str, areas: Counter) -> str:
    return area.replace("_", " ").title()


@dataclass
class AssignResult:
    cluster_id: str
    created: bool
    promoted: bool


class IncrementalClusterer:
    def __init__(self, similarity_threshold: float = 0.55, min_cluster_size: int = 3,
                 emerging_window: float = 24 * 3600) -> None:
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        self.emerging_window = emerging_window
        self._live: dict[str, _Live] = {}

    # ---- persistence bridge ---------------------------------------------

    def load(self, clusters: Sequence[Cluster]) -> None:
        """Rehydrate centroids from stored clusters (for nightly incremental runs)."""
        for c in clusters:
            n = max(1, c.size)
            self._live[c.id] = _Live(cluster=c, sum_vec=[x * n for x in c.centroid], provisional=False)

    @property
    def clusters(self) -> list[Cluster]:
        return [lv.cluster for lv in self._live.values() if not lv.provisional]

    def all_clusters(self) -> list[Cluster]:
        return [lv.cluster for lv in self._live.values()]

    # ---- core streaming op ----------------------------------------------

    def _nearest(self, vec: Sequence[float]) -> tuple[Optional[str], float]:
        best_id, best_sim = None, -1.0
        for cid, lv in self._live.items():
            sim = cosine(vec, lv.cluster.centroid)
            if sim > best_sim:
                best_id, best_sim = cid, sim
        return best_id, best_sim

    def assign(self, et: EnrichedTicket) -> AssignResult:
        vec = et.embedding
        cid, sim = self._nearest(vec)
        created = promoted = False

        if cid is None or sim < self.similarity_threshold:
            cid = new_id("cl")
            cluster = Cluster(id=cid, label="(forming)", centroid=list(vec), emerging=True)
            self._live[cid] = _Live(cluster=cluster, sum_vec=list(vec))
            created = True

        lv = self._live[cid]
        lv.cluster.member_ids.append(et.ticket.id)
        for i, x in enumerate(vec):
            lv.sum_vec[i] += x
        lv.severities.append(et.enrichment.bug_severity)
        lv.sentiments.append(et.enrichment.sentiment)
        lv.churns.append(et.enrichment.churn_risk)
        lv.areas[et.enrichment.feature_area] += 1
        lv.recompute_centroid()
        lv.refresh_stats()

        if lv.provisional and lv.cluster.size >= self.min_cluster_size:
            lv.provisional = False
            promoted = True
        lv.cluster.emerging = (time.time() - lv.cluster.created_at) <= self.emerging_window

        et.cluster_id = cid
        return AssignResult(cluster_id=cid, created=created, promoted=promoted)

    def fit(self, tickets: Sequence[EnrichedTicket]) -> list[Cluster]:
        for et in tickets:
            self.assign(et)
        return self.clusters
