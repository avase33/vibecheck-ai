"""Message-queue abstraction for the ingestion worker.

Webhooks enqueue raw feedback; workers consume and run the pipeline. The default
:class:`InMemoryQueue` is a thread-safe FIFO that lets the whole producer→worker
path run in a single process (and in tests) with identical semantics to a real
broker. :class:`CeleryQueue` is the production adapter backed by Redis/RabbitMQ.
"""

from __future__ import annotations

import json
import queue as _q
import threading
from typing import Callable, Optional, Protocol

from ..errors import QueueError


class MessageQueue(Protocol):
    def publish(self, payload: dict) -> None: ...

    def consume(self, handler: Callable[[dict], None], max_messages: Optional[int] = None) -> int: ...


class InMemoryQueue:
    def __init__(self) -> None:
        self._q: "_q.Queue[Optional[str]]" = _q.Queue()
        self._stop = threading.Event()

    def publish(self, payload: dict) -> None:
        self._q.put(json.dumps(payload))

    def qsize(self) -> int:
        return self._q.qsize()

    def consume(self, handler: Callable[[dict], None], max_messages: Optional[int] = None) -> int:
        """Drain up to ``max_messages`` (or all currently queued) synchronously."""
        processed = 0
        while max_messages is None or processed < max_messages:
            try:
                raw = self._q.get_nowait()
            except _q.Empty:
                break
            if raw is None:
                break
            try:
                handler(json.loads(raw))
            except Exception as exc:  # keep the worker alive on a bad message
                raise QueueError(f"handler failed: {exc}") from exc
            processed += 1
        return processed

    def run_forever(self, handler: Callable[[dict], None], poll: float = 0.2) -> None:  # pragma: no cover
        while not self._stop.is_set():
            try:
                raw = self._q.get(timeout=poll)
            except _q.Empty:
                continue
            if raw is None:
                break
            handler(json.loads(raw))

    def stop(self) -> None:  # pragma: no cover
        self._stop.set()
        self._q.put(None)


class CeleryQueue:  # pragma: no cover - requires broker
    """Adapter that publishes to a Celery task over Redis/RabbitMQ."""

    def __init__(self, broker_url: str, task_name: str = "vibecheck.ingest") -> None:
        from celery import Celery  # type: ignore

        self._app = Celery("vibecheck", broker=broker_url, backend=broker_url)
        self._task_name = task_name

    def publish(self, payload: dict) -> None:
        self._app.send_task(self._task_name, args=[payload])

    def consume(self, handler, max_messages=None):
        raise QueueError("CeleryQueue is consumed by celery workers, not this method")


def build_queue(backend: str = "memory", url: str = "") -> MessageQueue:
    if backend == "celery" and url:
        return CeleryQueue(url)
    return InMemoryQueue()
