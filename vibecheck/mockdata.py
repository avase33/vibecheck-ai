"""Realistic synthetic feedback generator.

Produces messages that look like real support tickets and app-store reviews
across a set of product areas, with a controllable mix of bugs, feature requests,
praise, churn threats — and deliberate *noise* ("Hi", "Thanks!") so the noise
filter has something to earn its keep. Deterministic given a seed, so benchmarks
and demos are reproducible.
"""

from __future__ import annotations

import random
from typing import Iterator

from .core.models import Source, Ticket

# (feature area, templates). {v} is a random product-area noun where useful.
_BUGS = [
    ("authentication", "I can't log in anymore, it keeps saying invalid password even after I reset it."),
    ("authentication", "The 2FA code never arrives so I'm completely locked out of my account. Urgent!"),
    ("authentication", "SSO login through Okta is broken since the last update, error 500 every time."),
    ("billing", "I was charged twice this month for the same subscription, please refund the duplicate."),
    ("billing", "The invoice PDF download returns a 404, I need it for expenses."),
    ("performance", "The dashboard takes 30 seconds to load and the spinner just hangs forever."),
    ("performance", "App freezes constantly when I scroll the reports page, it's unusable now."),
    ("reliability", "Everything is down, I get a 500 error on every page. This is a critical outage."),
    ("mobile_app", "The iOS app crashes on launch after the latest update on my iPhone."),
    ("data_export", "CSV export is broken, the file comes out empty every single time."),
    ("integrations", "The Slack integration stopped posting notifications, the webhook just fails silently."),
    ("search", "Search returns no results even for tickets I know exist, the filter is clearly broken."),
    ("notifications", "I stopped getting email notifications for new comments, checked spam, nothing."),
]
_FEATURES = [
    ("data_export", "Would love the ability to schedule automatic CSV exports every week."),
    ("integrations", "Please add a native Salesforce integration, we really need it to sync deals."),
    ("ui_ux", "It would be great if you added a dark mode, the white screen hurts at night."),
    ("search", "Can you add saved search filters? I run the same query twenty times a day."),
    ("notifications", "A digest email option would be nice instead of one notification per event."),
    ("mobile_app", "Wish the mobile app had offline mode for when I'm on the train."),
    ("reporting", "Suggestion: let us build custom dashboards with our own metrics."),
]
_PRAISE = [
    ("onboarding", "The onboarding flow was so smooth, I was up and running in five minutes. Love it!"),
    ("performance", "Latest update made everything super fast, great work team!"),
    ("ui_ux", "The new design is beautiful and really intuitive, thank you!"),
    ("integrations", "The Zapier integration is a lifesaver, saved us hours every week."),
]
_CHURN = [
    ("billing", "This is unacceptable, I've been overcharged three times. I'm cancelling and switching to a competitor."),
    ("reliability", "Third outage this month. We're done with this, moving our team elsewhere."),
    ("performance", "So slow and buggy, complete waste of money. Requesting a refund and cancelling."),
    ("authentication", "Locked out for two days with no support. Cancelling my subscription, worst experience ever."),
]
_NOISE = [
    "Hi", "Thanks!", "Thank you so much", "ok", "okay", "Any update?", "hello?",
    "Great, thanks!", "👍", "This is an automated out of office reply.",
    "https://example.com/status", "cheers", "np", "Sounds good.",
]

_SOURCES = [s.value for s in Source]
_CHANNELS = ["support", "app_review", "in_app", "email", "community"]


def generate(n: int, seed: int = 7, noise_ratio: float = 0.18) -> Iterator[Ticket]:
    rng = random.Random(seed)
    pools = [
        (0.42, _BUGS),
        (0.20, _FEATURES),
        (0.12, _PRAISE),
        (0.08, _CHURN),
    ]
    for i in range(n):
        r = rng.random()
        if r < noise_ratio:
            text = rng.choice(_NOISE)
        else:
            pick = rng.random()
            cum = 0.0
            chosen = _BUGS
            for weight, pool in pools:
                cum += weight
                if pick <= cum:
                    chosen = pool
                    break
            _, text = rng.choice(chosen)
            # light variation so identical strings don't dominate (but some repeat, exercising the cache)
            if rng.random() < 0.5:
                text = text + rng.choice(["", " Please help.", " Thanks.", " This is frustrating.", ""])
        yield Ticket(
            text=text,
            source=rng.choice(_SOURCES),
            channel=rng.choice(_CHANNELS),
            customer_id=f"cust_{rng.randint(1, max(1, n // 5))}",
        )


def generate_events(n: int, seed: int = 7, noise_ratio: float = 0.18) -> Iterator[dict]:
    for t in generate(n, seed=seed, noise_ratio=noise_ratio):
        yield {"text": t.text, "source": t.source, "channel": t.channel, "customer_id": t.customer_id}
