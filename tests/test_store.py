from vibecheck.core.embeddings import HashingEmbedder
from vibecheck.core.enrichment import MockEnricher
from vibecheck.core.models import Alert, EnrichedTicket, Ticket
from vibecheck.storage.store import Store


def _store(tmp_path):
    return Store(str(tmp_path / "t.db"))


def _et(text):
    return EnrichedTicket(ticket=Ticket(text=text),
                          enrichment=MockEnricher().enrich(text),
                          embedding=HashingEmbedder(dim=64).embed(text))


def test_save_and_iter_enriched(tmp_path):
    s = _store(tmp_path)
    s.save_enriched(_et("billing charge is wrong"))
    s.save_noise(Ticket(text="Hi"), "greeting_or_ack")
    assert s.count_tickets(exclude_noise=True) == 1
    rows = s.iter_enriched()
    assert len(rows) == 1
    assert rows[0].enrichment.feature_area == "billing"
    s.close()


def test_feature_area_breakdown(tmp_path):
    s = _store(tmp_path)
    for t in ["billing invoice wrong", "billing double charge", "cannot log in password"]:
        s.save_enriched(_et(t))
    breakdown = {b["feature_area"]: b["count"] for b in s.feature_area_breakdown()}
    assert breakdown.get("billing") == 2
    assert breakdown.get("authentication") == 1
    s.close()


def test_alerts_roundtrip(tmp_path):
    s = _store(tmp_path)
    s.save_alert(Alert(cluster_id="c1", severity=5, title="outage", detail="down", channels=["slack", "jira"]))
    recent = s.recent_alerts()
    assert len(recent) == 1
    assert recent[0].channels == ["slack", "jira"]
    s.close()


def test_stats(tmp_path):
    s = _store(tmp_path)
    s.save_enriched(_et("app crashes with a 500 error"))
    s.save_noise(Ticket(text="thanks"), "greeting_or_ack")
    st = s.stats()
    assert st["total_tickets"] == 2
    assert st["noise_filtered"] == 1
    assert st["bugs"] >= 1
    s.close()
