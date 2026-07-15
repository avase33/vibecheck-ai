"""Self-healing noise filter.

Support streams are full of content-free messages — "Hi", "Thanks!", "ok",
"any update?", bot auto-replies, out-of-office bounces. Embedding and clustering
those wastes vector-DB writes and pollutes topics. This filter drops them
*before* they hit the pipeline, using cheap deterministic heuristics (no model),
and explains *why* each message was dropped so the decision is auditable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .tokenizer import tokenize

_GREETINGS = frozenset("""
hi hello hey yo hiya heya greetings thanks thank thankyou ty cheers ok okay k
kk cool nice great awesome perfect done yep yes no nope sure fine bye goodbye
regards best sincerely np welcome sorry oops lol
""".split())

_AUTO_PATTERNS = [
    re.compile(r"out of office", re.I),
    re.compile(r"automatic(?:ally)? repl", re.I),
    re.compile(r"do not reply", re.I),
    re.compile(r"unsubscribe", re.I),
    re.compile(r"delivery (?:status|has failed)", re.I),
    re.compile(r"this is an automated", re.I),
]

_URL_ONLY = re.compile(r"^\s*(?:https?://\S+\s*)+$", re.I)


@dataclass
class NoiseVerdict:
    is_noise: bool
    reason: str = ""


def classify(text: str) -> NoiseVerdict:
    raw = (text or "").strip()
    if not raw:
        return NoiseVerdict(True, "empty")
    if len(raw) < 3:
        return NoiseVerdict(True, "too_short")
    if _URL_ONLY.match(raw):
        return NoiseVerdict(True, "url_only")
    for pat in _AUTO_PATTERNS:
        if pat.search(raw):
            return NoiseVerdict(True, "automated_message")

    toks = tokenize(raw, keep_stopwords=True)
    if not toks:
        return NoiseVerdict(True, "no_content_tokens")

    content = [t for t in toks if t not in _GREETINGS and not (t.startswith("_") and t.endswith("_"))]
    # Pure pleasantries / acknowledgements with no substantive token.
    if not content and len(toks) <= 6:
        return NoiseVerdict(True, "greeting_or_ack")
    # Very short and mostly greeting words.
    if len(content) <= 1 and len(toks) <= 4:
        return NoiseVerdict(True, "low_signal")
    return NoiseVerdict(False, "")


def is_noise(text: str) -> bool:
    return classify(text).is_noise
