"""Alerting agent — a small LangGraph-style state machine.

Runs over clusters produced by the analytics batch and decides, node by node,
whether a topic warrants human attention and where to route it:

    triage → (severe? spiking? churny?) → compose → dispatch(slack|jira)

Each node is a pure function of an :class:`AgentState`, mirroring how a LangGraph
graph transitions state; the conditional edges are the routing rules. Dispatchers
are pluggable — the defaults are deterministic mocks that record what *would* be
sent, and real Slack/Jira adapters slot in behind the same interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from ..core.models import Alert, Cluster
from ..logging_setup import get_logger

log = get_logger("agent")

Dispatcher = Callable[[Alert], str]


# ---- dispatchers ---------------------------------------------------------

class MockSlackDispatcher:
    def __init__(self) -> None:
        self.sent: list[Alert] = []

    def __call__(self, alert: Alert) -> str:
        self.sent.append(alert)
        log.info("[slack] %s (sev %d)", alert.title, alert.severity)
        return f"slack://posted/{alert.id}"


class MockJiraDispatcher:
    def __init__(self) -> None:
        self.sent: list[Alert] = []
        self._n = 0

    def __call__(self, alert: Alert) -> str:
        self._n += 1
        self.sent.append(alert)
        key = f"BUG-{1000 + self._n}"
        log.info("[jira] created %s: %s", key, alert.title)
        return key


class SlackWebhookDispatcher:  # pragma: no cover - network
    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def __call__(self, alert: Alert) -> str:
        import json
        import urllib.request

        body = json.dumps({"text": f":rotating_light: *{alert.title}* (sev {alert.severity})\n{alert.detail}"}).encode()
        req = urllib.request.Request(self.webhook_url, data=body, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)  # noqa: S310
        return "slack://posted"


# ---- agent state machine -------------------------------------------------

@dataclass
class AgentState:
    cluster: Cluster
    severity_threshold: int = 4
    route_slack: bool = False
    route_jira: bool = False
    reasons: list[str] = field(default_factory=list)
    alert: Optional[Alert] = None
    result: dict = field(default_factory=dict)


def node_triage(s: AgentState) -> AgentState:
    c = s.cluster
    if c.avg_severity >= s.severity_threshold:
        s.route_jira = True
        s.route_slack = True
        s.reasons.append(f"avg severity {c.avg_severity:.1f} >= {s.severity_threshold}")
    if c.emerging and c.size >= 3:
        s.route_slack = True
        s.reasons.append("emerging topic gaining volume")
    if c.high_churn_share >= 0.34:
        s.route_slack = True
        s.reasons.append(f"{round(c.high_churn_share*100)}% high churn-risk")
    return s


def node_compose(s: AgentState) -> AgentState:
    if not (s.route_slack or s.route_jira):
        return s
    c = s.cluster
    title = f"[{c.dominant_feature_area or c.label}] {c.size} reports, sev {c.avg_severity:.1f}"
    detail = (f"Topic '{c.label}' — {c.size} tickets, avg severity {c.avg_severity:.1f}, "
              f"sentiment {c.avg_sentiment:+.2f}, churn-risk {round(c.high_churn_share*100)}%. "
              f"Triggered by: {'; '.join(s.reasons)}.")
    channels = [ch for ch, on in (("slack", s.route_slack), ("jira", s.route_jira)) if on]
    s.alert = Alert(cluster_id=c.id, severity=int(round(c.avg_severity)),
                    title=title, detail=detail, channels=channels)
    return s


class AlertingAgent:
    def __init__(self, severity_threshold: int = 4,
                 slack: Optional[Dispatcher] = None, jira: Optional[Dispatcher] = None) -> None:
        self.severity_threshold = severity_threshold
        self.slack = slack or MockSlackDispatcher()
        self.jira = jira or MockJiraDispatcher()

    def run(self, cluster: Cluster) -> Optional[Alert]:
        state = AgentState(cluster=cluster, severity_threshold=self.severity_threshold)
        state = node_compose(node_triage(state))
        if state.alert is None:
            return None
        if state.route_slack:
            state.result["slack"] = self.slack(state.alert)
        if state.route_jira:
            state.result["jira"] = self.jira(state.alert)
        return state.alert

    def run_many(self, clusters, store=None) -> list[Alert]:
        alerts = []
        for c in clusters:
            a = self.run(c)
            if a is not None:
                alerts.append(a)
                if store is not None:
                    store.save_alert(a)
        return alerts
