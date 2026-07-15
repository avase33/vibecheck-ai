from vibecheck.core.cache import EnrichmentCache, InMemoryCache, cache_key
from vibecheck.core.enrichment import MockEnricher, validate_enrichment
from vibecheck.core.models import ChurnRisk
from vibecheck.errors import EnrichmentError
import pytest


def test_mock_enricher_guarantees_valid_schema():
    e = MockEnricher()
    enr = e.enrich("I was charged twice and I want a refund, this is unacceptable, cancelling")
    assert enr.feature_area == "billing"
    assert 0 <= enr.bug_severity <= 5
    assert enr.churn_risk in {c.value for c in ChurnRisk}
    assert -1.0 <= enr.sentiment <= 1.0


def test_mock_enricher_detects_bug_and_severity():
    e = MockEnricher()
    enr = e.enrich("URGENT: everything is down, 500 error on every page, data loss!")
    assert enr.is_bug
    assert enr.bug_severity == 5


def test_mock_enricher_feature_request():
    e = MockEnricher()
    enr = e.enrich("Would love the ability to schedule automatic CSV exports")
    assert enr.is_feature_request
    assert enr.feature_area == "data_export"


def test_validate_enrichment_repairs_bad_enum():
    enr = validate_enrichment('{"feature_area":"billing","bug_severity":9,"churn_risk":"???","sentiment":5}')
    assert enr.bug_severity == 5          # clamped
    assert enr.sentiment == 1.0           # clamped
    assert enr.churn_risk == "low"        # repaired


def test_validate_enrichment_rejects_non_json():
    with pytest.raises(EnrichmentError):
        validate_enrichment("no json here")


def test_cache_hit_and_miss_stats():
    calls = {"n": 0}

    def compute(text):
        calls["n"] += 1
        return MockEnricher().enrich(text)

    cache = EnrichmentCache(InMemoryCache())
    cache.get_or_compute("app crashes", compute)
    cache.get_or_compute("app crashes", compute)   # identical -> hit
    cache.get_or_compute("APP CRASHES ", compute)   # normalised -> hit
    assert calls["n"] == 1
    assert cache.stats.hits == 2
    assert cache.stats.misses == 1
    assert cache.stats.hit_rate > 0.6


def test_cache_key_normalisation():
    assert cache_key("Hello   World") == cache_key("hello world")
