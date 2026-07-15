"""Deterministic metadata enrichment (Instructor / structured-output style).

Every ticket must yield a *valid* :class:`~vibecheck.core.models.Enrichment`
object with ``feature_area``, ``bug_severity``, ``churn_risk`` and friends — no
free-form prose, no missing keys, no invalid enums. That guarantee is what makes
the whole platform aggregatable.

Two backends:

* :class:`MockEnricher` — a fast, deterministic lexical classifier used offline
  and in CI. Zero dependencies, fully reproducible.
* :class:`AnthropicEnricher` — calls Claude and *validates/repairs* the JSON
  against the same schema, so even the LLM path can never emit a malformed
  record (falls back to the mock on any failure).
"""

from __future__ import annotations

import json
import re
from typing import Protocol

from ..errors import EnrichmentError
from .models import ChurnRisk, Enrichment

# --- lexicons -------------------------------------------------------------

FEATURE_AREAS: dict[str, tuple[str, ...]] = {
    "authentication": ("login", "log in", "signin", "sign in", "password", "2fa", "otp", "sso", "auth", "logout", "session"),
    "billing": ("bill", "invoice", "charge", "payment", "refund", "subscription", "pricing", "card", "receipt", "coupon"),
    "performance": ("slow", "lag", "latency", "loading", "timeout", "freeze", "hang", "crash", "spinner", "unresponsive"),
    "notifications": ("notification", "email", "alert", "push", "reminder", "digest"),
    "search": ("search", "filter", "sort", "query", "results", "find"),
    "mobile_app": ("android", "ios", "iphone", "ipad", "mobile app", "play store", "app store"),
    "data_export": ("export", "download", "csv", "report", "pdf", "backup", "import"),
    "integrations": ("integration", "webhook", "api", "zapier", "slack", "salesforce", "sync", "connector"),
    "ui_ux": ("button", "layout", "screen", "page", "dark mode", "design", "confusing", "ui", "interface"),
    "onboarding": ("onboarding", "setup", "getting started", "tutorial", "walkthrough", "first time"),
    "reliability": ("down", "outage", "500", "error", "broken", "failed", "not working", "bug", "glitch"),
}

_BUG_WORDS = ("bug", "broken", "crash", "error", "fail", "not working", "doesn't work",
              "doesnt work", "glitch", "freeze", "500", "404", "cannot", "can't", "unable", "wrong")
_FEATURE_WORDS = ("please add", "would love", "feature request", "wish", "it would be great",
                  "can you add", "suggestion", "should have", "need the ability", "would be nice", "hope you add")
_SEVERITY_CRITICAL = ("data loss", "lost all", "charged twice", "double charged", "security", "breach",
                      "cannot login", "can't login", "locked out", "outage", "everything is down", "urgent", "asap")
_CHURN_WORDS = ("cancel", "canceling", "cancelling", "refund", "switch to", "competitor", "unacceptable",
                "done with", "leaving", "unsubscribe", "worst", "useless", "waste of money", "never again")

_POS = ("love", "great", "awesome", "excellent", "perfect", "amazing", "thank", "helpful", "nice", "good", "fast", "smooth")
_NEG = ("hate", "terrible", "awful", "worst", "broken", "useless", "frustrat", "angry", "annoying", "slow", "bad", "poor", "disappointed")


class Enricher(Protocol):
    def enrich(self, text: str) -> Enrichment: ...


def _score(text: str, words) -> int:
    return sum(1 for w in words if w in text)


class MockEnricher:
    """Deterministic lexical enricher — reproducible and dependency-free."""

    def enrich(self, text: str) -> Enrichment:
        t = (text or "").lower()

        # feature area = best lexical match, default reliability/other
        best_area, best_hits = "other", 0
        for area, kws in FEATURE_AREAS.items():
            hits = sum(1 for k in kws if k in t)
            if hits > best_hits:
                best_area, best_hits = area, hits

        is_bug = _score(t, _BUG_WORDS) > 0
        is_feature = _score(t, _FEATURE_WORDS) > 0

        pos, neg = _score(t, _POS), _score(t, _NEG)
        total = pos + neg
        sentiment = 0.0 if total == 0 else (pos - neg) / total

        # severity 0..5
        sev = 0
        if is_bug:
            sev = 3
        if _score(t, _SEVERITY_CRITICAL) > 0:
            sev = 5
        if any(w in t for w in ("urgent", "asap", "immediately", "critical", "emergency")):
            sev = max(sev, 4)
        if neg > pos and sev < 2 and (is_bug or neg >= 2):
            sev = 2
        sev = max(0, min(5, sev))

        # churn risk
        churn_hits = _score(t, _CHURN_WORDS)
        if churn_hits >= 1 and (sev >= 4 or sentiment <= -0.5):
            churn = ChurnRisk.HIGH.value
        elif churn_hits >= 1 or sentiment <= -0.6 or sev >= 4:
            churn = ChurnRisk.MEDIUM.value
        else:
            churn = ChurnRisk.LOW.value

        summary = _summarize(text, best_area, is_bug, is_feature)
        return Enrichment(
            feature_area=best_area, is_bug=is_bug, is_feature_request=is_feature,
            bug_severity=sev, sentiment=sentiment, churn_risk=churn, summary=summary,
        )


def _summarize(text: str, area: str, is_bug: bool, is_feature: bool) -> str:
    kind = "Bug" if is_bug else ("Feature request" if is_feature else "Feedback")
    snippet = re.sub(r"\s+", " ", (text or "").strip())
    if len(snippet) > 90:
        snippet = snippet[:87] + "..."
    return f"{kind} re: {area.replace('_', ' ')} — {snippet}"


class AnthropicEnricher:
    """LLM enrichment with strict schema validation and repair."""

    SYSTEM = (
        "You classify a single customer feedback message. Respond with ONLY a JSON object "
        "with keys: feature_area (string), is_bug (bool), is_feature_request (bool), "
        "bug_severity (int 0-5), sentiment (float -1..1), churn_risk (low|medium|high), "
        "summary (string). No prose."
    )

    def __init__(self, model: str = "claude-3-5-sonnet-latest", api_key: str | None = None) -> None:
        import anthropic  # type: ignore

        self._client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        self._model = model
        self._fallback = MockEnricher()

    def enrich(self, text: str) -> Enrichment:
        try:
            msg = self._client.messages.create(
                model=self._model, max_tokens=400, system=self.SYSTEM,
                messages=[{"role": "user", "content": text}],
            )
            raw = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            return validate_enrichment(raw)
        except Exception:
            # Never emit a malformed record — degrade to the deterministic path.
            return self._fallback.enrich(text)


def validate_enrichment(raw: str) -> Enrichment:
    """Parse + coerce arbitrary JSON into a valid Enrichment or raise."""
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise EnrichmentError("no JSON object in model output")
    try:
        data = json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise EnrichmentError(f"invalid JSON: {exc}") from exc

    churn = str(data.get("churn_risk", "low")).lower()
    if churn not in (c.value for c in ChurnRisk):
        churn = ChurnRisk.LOW.value
    try:
        sev = max(0, min(5, int(data.get("bug_severity", 0))))
        sentiment = max(-1.0, min(1.0, float(data.get("sentiment", 0.0))))
    except (TypeError, ValueError) as exc:
        raise EnrichmentError(f"bad numeric field: {exc}") from exc

    return Enrichment(
        feature_area=str(data.get("feature_area", "other")) or "other",
        is_bug=bool(data.get("is_bug", False)),
        is_feature_request=bool(data.get("is_feature_request", False)),
        bug_severity=sev, sentiment=sentiment, churn_risk=churn,
        summary=str(data.get("summary", ""))[:200],
    )


def build_enricher(backend: str = "mock", model: str = "claude-3-5-sonnet-latest") -> Enricher:
    if backend == "anthropic":
        return AnthropicEnricher(model=model)
    return MockEnricher()
