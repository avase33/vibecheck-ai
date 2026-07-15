"""A small, dependency-free tokenizer with domain-aware normalisation.

Handles the messy reality of support text: URLs, emails, order/ticket ids,
version numbers and error codes are collapsed to stable placeholder tokens so
they do not blow up the vocabulary, while stopwords are removed. This keeps the
downstream hashing embeddings focused on the *topical* content of a message.
"""

from __future__ import annotations

import re

_STOPWORDS = frozenset("""
a an the and or but if then else of to in on at for from by with without about
is are was were be been being do does did doing have has had having i you he she
it we they me my your our their this that these those as so too very just can
could would should will shall may might must not no yes there here what which who
whom when where why how am pm please thanks thank hi hello hey regards
""".split())

_URL = re.compile(r"https?://\S+")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_VERSION = re.compile(r"\bv?\d+\.\d+(?:\.\d+)*\b")
_ORDERID = re.compile(r"\b(?:#|order|ticket|txn|inv)[-_ ]?\d{3,}\b", re.I)
_ERRCODE = re.compile(r"\b(?:err|error|code|http)[-_ ]?\d{3,}\b", re.I)
_NUM = re.compile(r"\b\d+\b")
# token = a placeholder (_word_) OR an ordinary word
_TOKEN = re.compile(r"_[a-z]+_|[a-z][a-z'+-]*")

_PLACEHOLDERS = frozenset(["_url_", "_email_", "_orderid_", "_errcode_", "_version_", "_num_"])


def normalize(text: str) -> str:
    t = text.lower()
    t = _URL.sub(" _url_ ", t)
    t = _EMAIL.sub(" _email_ ", t)
    t = _ORDERID.sub(" _orderid_ ", t)
    t = _ERRCODE.sub(" _errcode_ ", t)
    t = _VERSION.sub(" _version_ ", t)
    t = _NUM.sub(" _num_ ", t)
    return t


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    toks: list[str] = []
    for m in _TOKEN.finditer(normalize(text)):
        w = m.group(0)
        if w in _PLACEHOLDERS:
            toks.append(w)
            continue
        if len(w) < 2:
            continue
        if not keep_stopwords and w in _STOPWORDS:
            continue
        toks.append(w)
    return toks


def bigrams(tokens: list[str]) -> list[str]:
    return [f"{a}_{b}" for a, b in zip(tokens, tokens[1:])]
