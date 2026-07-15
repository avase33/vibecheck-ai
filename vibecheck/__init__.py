"""VibeCheck-AI — Enterprise Customer Intelligence Engine.

Ingests unstructured customer feedback (support tickets, reviews, chats),
enriches it into structured signals, clusters recurring complaints with
incremental unsupervised ML, and routes urgent issues to engineering — turning
noise into an auto-updating product roadmap.

Offline-first: deterministic mocks stand in for the LLM, the embedding model, and
the message broker, so the whole pipeline runs and is testable with no external
infrastructure. Real adapters (Anthropic Claude, sentence-transformers, HDBSCAN,
Celery/Redis, Qdrant, Slack/Jira) wire in for production.
"""

from .config import Settings
from .core.models import Alert, Cluster, EnrichedTicket, Enrichment, Ticket
from .engine import VibeCheck
from .pipeline import FeedbackPipeline
from .version import __version__

__all__ = [
    "__version__", "Settings", "VibeCheck", "FeedbackPipeline",
    "Ticket", "Enrichment", "EnrichedTicket", "Cluster", "Alert",
]
