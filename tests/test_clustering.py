from vibecheck.core.clustering import IncrementalClusterer
from vibecheck.core.embeddings import HashingEmbedder
from vibecheck.core.enrichment import MockEnricher
from vibecheck.core.models import EnrichedTicket, Ticket


def _enriched(text):
    emb = HashingEmbedder(dim=256)
    return EnrichedTicket(ticket=Ticket(text=text),
                          enrichment=MockEnricher().enrich(text),
                          embedding=emb.embed(text))


def test_similar_tickets_form_one_cluster():
    clu = IncrementalClusterer(similarity_threshold=0.3, min_cluster_size=2)
    texts = [
        "login password broken, cannot login with my password",
        "login password broken, my login password does not work",
        "login password broken, login rejects the password",
    ]
    for t in texts:
        clu.assign(_enriched(t))
    promoted = clu.clusters
    assert len(promoted) == 1
    assert promoted[0].size == 3
    assert promoted[0].dominant_feature_area == "authentication"


def test_distinct_topics_form_distinct_clusters():
    clu = IncrementalClusterer(similarity_threshold=0.5, min_cluster_size=1)
    a = _enriched("please add dark mode to the mobile app")
    b = _enriched("I was double charged on my invoice, refund please")
    clu.assign(a)
    clu.assign(b)
    assert len({a.cluster_id, b.cluster_id}) == 2


def test_provisional_clusters_need_min_size():
    clu = IncrementalClusterer(similarity_threshold=0.4, min_cluster_size=3)
    r = clu.assign(_enriched("dashboard is very slow and laggy"))
    assert r.created
    # only one member so far -> not promoted, not in .clusters
    assert clu.clusters == []
    assert len(clu.all_clusters()) == 1


def test_load_rehydrates_centroids():
    clu = IncrementalClusterer(similarity_threshold=0.3, min_cluster_size=2)
    for t in ["billing invoice charge wrong", "billing invoice charge problem"]:
        clu.assign(_enriched(t))
    saved = clu.clusters
    clu2 = IncrementalClusterer(similarity_threshold=0.3, min_cluster_size=2)
    clu2.load(saved)
    # a new similar ticket should join the rehydrated cluster, not spawn a new one
    r = clu2.assign(_enriched("billing invoice charge is wrong"))
    assert r.cluster_id == saved[0].id
