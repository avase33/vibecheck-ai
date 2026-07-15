from vibecheck.config import Settings
from vibecheck.core.models import Cluster, Ticket
from vibecheck.engine import VibeCheck
from vibecheck.mockdata import generate, generate_events
from vibecheck.services.agent import AlertingAgent, MockJiraDispatcher, MockSlackDispatcher
from vibecheck.services.analytics import roadmap_score
from vibecheck.services.ingestion import IngestionWorker, ticket_from_event


def _engine(tmp_path):
    s = Settings()
    s.database_url = str(tmp_path / "vc.db")
    s.min_cluster_size = 2
    return VibeCheck(s)


def test_pipeline_filters_noise_and_enriches(tmp_path):
    vc = _engine(tmp_path)
    assert vc.ingest(Ticket(text="Thanks!")).accepted is False
    r = vc.ingest(Ticket(text="I can't log in, the password reset is broken"))
    assert r.accepted is True
    rows = vc.store.iter_enriched()
    assert rows[0].enrichment.feature_area == "authentication"
    vc.close()


def test_end_to_end_demo_produces_roadmap(tmp_path):
    vc = _engine(tmp_path)
    vc.ingest_many(generate(600, seed=3))
    clusters = vc.analytics.rebuild()
    assert len(clusters) > 0
    roadmap = vc.roadmap(limit=10)
    assert roadmap
    # scores are sorted descending
    scores = [it.score for it in roadmap]
    assert scores == sorted(scores, reverse=True)
    stats = vc.stats()
    assert stats["noise_filtered"] > 0          # noise filter earned its keep
    assert stats["cache"]["hits"] > 0           # repeated templates hit the cache
    vc.close()


def test_ingestion_worker_drains_queue(tmp_path):
    vc = _engine(tmp_path)
    worker = IngestionWorker(vc.pipeline)
    for evt in generate_events(120, seed=5):
        worker.submit(evt)
    processed = worker.drain()
    assert processed == 120
    assert worker.stats.accepted + worker.stats.noise == 120
    assert worker.stats.noise > 0
    vc.close()


def test_ticket_from_event_maps_fields():
    t = ticket_from_event({"body": "app crashes", "platform": "intercom", "author": "u1"})
    assert t.text == "app crashes"
    assert t.source == "intercom"
    assert t.customer_id == "u1"


def test_agent_routes_severe_cluster_to_slack_and_jira():
    slack, jira = MockSlackDispatcher(), MockJiraDispatcher()
    agent = AlertingAgent(severity_threshold=4, slack=slack, jira=jira)
    c = Cluster(id="c1", label="Reliability", centroid=[], member_ids=["a", "b", "c", "d"],
                dominant_feature_area="reliability", avg_severity=5.0, high_churn_share=0.5, emerging=True)
    alert = agent.run(c)
    assert alert is not None
    assert "slack" in alert.channels and "jira" in alert.channels
    assert len(slack.sent) == 1 and len(jira.sent) == 1


def test_agent_ignores_calm_cluster():
    agent = AlertingAgent(severity_threshold=4)
    c = Cluster(id="c2", label="UI", centroid=[], member_ids=["a", "b"],
                dominant_feature_area="ui_ux", avg_severity=1.0, avg_sentiment=0.3,
                high_churn_share=0.0, emerging=False)
    assert agent.run(c) is None


def test_roadmap_score_prioritises_severe_churny_topics():
    hot = Cluster(id="h", label="x", centroid=[], member_ids=list(range(20)),
                  avg_severity=5, avg_sentiment=-0.8, high_churn_share=0.6, emerging=True)
    calm = Cluster(id="c", label="y", centroid=[], member_ids=["a"],
                   avg_severity=1, avg_sentiment=0.5, high_churn_share=0.0)
    assert roadmap_score(hot, 20)[0] > roadmap_score(calm, 20)[0]
