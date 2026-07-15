"""Exception hierarchy for VibeCheck-AI."""

from __future__ import annotations


class VibeCheckError(Exception):
    """Base class for all VibeCheck errors."""


class ConfigError(VibeCheckError):
    """Invalid configuration."""


class EnrichmentError(VibeCheckError):
    """The enrichment step produced invalid structured output."""


class QueueError(VibeCheckError):
    """Message-queue transport failure."""


class StorageError(VibeCheckError):
    """Persistence failure."""
