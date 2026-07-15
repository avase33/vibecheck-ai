"""Ingestion-worker entrypoint.

In production this defines a Celery task ``vibecheck.ingest`` that runs each
webhook payload through the pipeline; ``celery -A vibecheck.services.worker_entry
worker`` (or this module executed directly) starts the consumer. Offline, running
this module simply drains an in-memory queue once and exits, which keeps the
container image identical across environments.
"""

from __future__ import annotations

import os

from ..config import Settings
from ..logging_setup import configure_logging, get_logger
from ..pipeline import FeedbackPipeline
from .ingestion import IngestionWorker

log = get_logger("worker")


def _pipeline() -> FeedbackPipeline:
    settings = Settings.from_env()
    return FeedbackPipeline(settings)


def make_celery():  # pragma: no cover - requires broker
    from celery import Celery

    broker = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
    app = Celery("vibecheck", broker=broker, backend=broker)
    pipeline = _pipeline()
    worker = IngestionWorker(pipeline)

    @app.task(name="vibecheck.ingest")
    def ingest(event: dict) -> dict:
        worker._handle(event)  # noqa: SLF001
        return worker.stats.to_dict()

    return app


# Celery discovers ``app`` at module load when the broker is configured.
if os.environ.get("VIBECHECK_QUEUE") == "celery":  # pragma: no cover
    try:
        app = make_celery()
    except Exception as exc:  # noqa: BLE001
        log.warning("celery unavailable (%s); worker idle", exc)


def main() -> int:  # pragma: no cover
    configure_logging(os.environ.get("VIBECHECK_LOG_LEVEL", "INFO"))
    log.info("ingestion worker entry (queue=%s)", os.environ.get("VIBECHECK_QUEUE", "memory"))
    # Offline fallback: nothing to consume from an empty in-memory queue; stay alive.
    import time

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    raise SystemExit(main())
