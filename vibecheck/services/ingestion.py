"""Ingestion worker.

Consumes raw feedback events from the queue (produced by inbound webhooks) and
runs each through the :class:`~vibecheck.pipeline.FeedbackPipeline`. In
production this is a Celery worker fanned out across many processes; offline it
drains an in-memory queue. Either way the per-message logic is identical.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..core.models import Source, Ticket
from ..logging_setup import get_logger
from ..pipeline import FeedbackPipeline
from .queue import InMemoryQueue, MessageQueue

log = get_logger("ingestion")


@dataclass
class WorkerStats:
    consumed: int = 0
    accepted: int = 0
    noise: int = 0
    cache_hits: int = 0

    def to_dict(self) -> dict:
        return {"consumed": self.consumed, "accepted": self.accepted, "noise": self.noise,
                "cache_hits": self.cache_hits}


def ticket_from_event(evt: dict) -> Ticket:
    """Map a webhook payload (Zendesk/Intercom/app-store shape) to a Ticket."""
    text = (evt.get("text") or evt.get("body") or evt.get("comment") or evt.get("review") or "").strip()
    source = evt.get("source") or evt.get("platform") or Source.OTHER.value
    return Ticket(
        text=text, source=str(source),
        channel=evt.get("channel", "support"),
        customer_id=str(evt.get("customer_id") or evt.get("author") or ""),
        metadata={k: v for k, v in evt.items() if k not in ("text", "body", "comment", "review")},
    )


class IngestionWorker:
    def __init__(self, pipeline: FeedbackPipeline, queue: Optional[MessageQueue] = None) -> None:
        self.pipeline = pipeline
        self.queue = queue or InMemoryQueue()
        self.stats = WorkerStats()

    def submit(self, event: dict) -> None:
        self.queue.publish(event)

    def _handle(self, event: dict) -> None:
        ticket = ticket_from_event(event)
        if not ticket.text:
            self.stats.consumed += 1
            self.stats.noise += 1
            return
        res = self.pipeline.ingest(ticket)
        self.stats.consumed += 1
        if res.accepted:
            self.stats.accepted += 1
        else:
            self.stats.noise += 1
        self.stats.cache_hits += res.cache_hit_before

    def drain(self, max_messages: Optional[int] = None) -> int:
        return self.queue.consume(self._handle, max_messages=max_messages)

    def run_forever(self) -> None:  # pragma: no cover
        log.info("ingestion worker started")
        self.queue.run_forever(self._handle)  # type: ignore[attr-defined]
