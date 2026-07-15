import math

from vibecheck.core import tokenizer
from vibecheck.core.embeddings import HashingEmbedder, centroid, cosine
from vibecheck.core.noise import classify, is_noise


def test_tokenizer_normalises_placeholders():
    toks = tokenizer.tokenize("Email me at a@b.com about order #12345 on v2.3.1")
    assert "_email_" in toks
    assert "_orderid_" in toks
    assert "_version_" in toks
    # stopwords removed
    assert "me" not in toks and "on" not in toks


def test_tokenizer_bigrams():
    assert tokenizer.bigrams(["a", "b", "c"]) == ["a_b", "b_c"]


def test_hashing_embedder_is_unit_length_and_deterministic():
    emb = HashingEmbedder(dim=128)
    v1 = emb.embed("the app keeps crashing on launch")
    v2 = emb.embed("the app keeps crashing on launch")
    assert v1 == v2
    assert abs(math.sqrt(sum(x * x for x in v1)) - 1.0) < 1e-9


def test_cosine_similarity_orders_by_topic():
    emb = HashingEmbedder(dim=256)
    a = emb.embed("I cannot log in, password reset is broken")
    b = emb.embed("login is broken, can't sign in with my password")
    c = emb.embed("please add a dark mode to the mobile app")
    assert cosine(a, b) > cosine(a, c)


def test_centroid_is_normalised():
    emb = HashingEmbedder(dim=64)
    vecs = [emb.embed(t) for t in ["billing issue", "billing problem", "charged twice"]]
    ctr = centroid(vecs)
    assert abs(math.sqrt(sum(x * x for x in ctr)) - 1.0) < 1e-9


def test_noise_filter_drops_greetings_and_keeps_signal():
    assert is_noise("Hi")
    assert is_noise("Thanks!")
    assert is_noise("   ")
    assert classify("This is an automated out of office reply.").reason == "automated_message"
    assert not is_noise("The dashboard crashes every time I open the reports page")


def test_noise_reasons():
    assert classify("").reason == "empty"
    assert classify("ok").is_noise
