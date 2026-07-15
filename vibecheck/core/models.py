"""Core domain models (dataclasses shared across the platform)."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


def new_id(prefix: str = "id") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class Source(str, Enum):
    ZENDESK = "zendesk"
    INTERCOM = "intercom"
    APP_STORE = "app_store"
    PLAY_STORE = "play_store"
    G2 = "g2"
    EMAIL = "email"
    OTHER = "other"


class ChurnRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class Ticket:
    text: str
    source: str = Source.OTHER.value
    channel: str = "support"
    customer_id: str = ""
    id: str = field(default_factory=lambda: new_id("tkt"))
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "text": self.text, "source": self.source, "channel": self.channel,
                "customer_id": self.customer_id, "created_at": self.created_at, "metadata": self.metadata}


@dataclass
class Enrichment:
    """Deterministic structured output guaranteed to be valid (Instructor-style)."""

    feature_area: str
    is_bug: bool
    is_feature_request: bool
    bug_severity: int          # 0..5
    sentiment: float           # -1..1
    churn_risk: str            # ChurnRisk
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {"feature_area": self.feature_area, "is_bug": self.is_bug,
                "is_feature_request": self.is_feature_request, "bug_severity": self.bug_severity,
                "sentiment": round(self.sentiment, 3), "churn_risk": self.churn_risk, "summary": self.summary}


@dataclass
class EnrichedTicket:
    ticket: Ticket
    enrichment: Enrichment
    embedding: list[float] = field(default_factory=list)
    cluster_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {**self.ticket.to_dict(), "enrichment": self.enrichment.to_dict(), "cluster_id": self.cluster_id}


@dataclass
class Cluster:
    id: str
    label: str
    centroid: list[float]
    member_ids: list[str] = field(default_factory=list)
    dominant_feature_area: str = ""
    avg_severity: float = 0.0
    avg_sentiment: float = 0.0
    high_churn_share: float = 0.0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    emerging: bool = False

    @property
    def size(self) -> int:
        return len(self.member_ids)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "label": self.label, "size": self.size,
                "dominant_feature_area": self.dominant_feature_area,
                "avg_severity": round(self.avg_severity, 2), "avg_sentiment": round(self.avg_sentiment, 3),
                "high_churn_share": round(self.high_churn_share, 3), "emerging": self.emerging}


@dataclass
class Alert:
    cluster_id: str
    severity: int
    title: str
    detail: str
    channels: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("alert"))
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "cluster_id": self.cluster_id, "severity": self.severity,
                "title": self.title, "detail": self.detail, "channels": self.channels}
