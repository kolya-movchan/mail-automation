"""Tests for retriever score filtering and result shape.

We stub the embedding model and Chroma collection so these tests are pure logic
and don't download models or hit disk.
"""

from __future__ import annotations

import retriever


class _FakeArray(list):
    def tolist(self):
        return list(self)


class _FakeModel:
    def encode(self, texts):
        return _FakeArray([[0.1, 0.2, 0.3]] * len(texts))


class _FakeCollection:
    def __init__(self, results):
        self._results = results

    def count(self):
        return len(self._results["documents"][0])

    def query(self, query_embeddings, n_results, include):
        return self._results


def _make_results(triples):
    """triples: list of (doc, meta, distance)."""
    docs, metas, dists = [], [], []
    for doc, meta, dist in triples:
        docs.append(doc)
        metas.append(meta)
        dists.append(dist)
    return {"documents": [docs], "metadatas": [metas], "distances": [dists]}


def test_retrieve_filters_below_min_score(monkeypatch):
    results = _make_results(
        [
            ("doc-strong", {"subject": "A"}, 0.10),  # score = 0.90 — keep
            ("doc-mid", {"subject": "B"}, 0.50),     # score = 0.50 — keep
            ("doc-weak", {"subject": "C"}, 0.85),    # score = 0.15 — drop
        ]
    )
    monkeypatch.setattr(retriever, "_get_model", lambda: _FakeModel())
    monkeypatch.setattr(retriever, "_get_collection", lambda: _FakeCollection(results))

    threads = retriever.retrieve("anything", n_results=3)

    assert len(threads) == 2
    assert [t["metadata"]["subject"] for t in threads] == ["A", "B"]
    assert threads[0]["score"] == 0.9
    assert threads[1]["score"] == 0.5


def test_retrieve_returns_empty_when_all_below_threshold(monkeypatch):
    results = _make_results([("doc", {"subject": "X"}, 0.95)])  # score 0.05
    monkeypatch.setattr(retriever, "_get_model", lambda: _FakeModel())
    monkeypatch.setattr(retriever, "_get_collection", lambda: _FakeCollection(results))

    assert retriever.retrieve("q", n_results=5) == []


def test_retrieve_respects_custom_min_score(monkeypatch):
    results = _make_results(
        [
            ("d1", {"subject": "A"}, 0.10),  # 0.90
            ("d2", {"subject": "B"}, 0.40),  # 0.60
        ]
    )
    monkeypatch.setattr(retriever, "_get_model", lambda: _FakeModel())
    monkeypatch.setattr(retriever, "_get_collection", lambda: _FakeCollection(results))

    threads = retriever.retrieve("q", n_results=2, min_score=0.75)
    assert len(threads) == 1
    assert threads[0]["metadata"]["subject"] == "A"
