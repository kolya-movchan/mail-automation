"""FastAPI endpoint tests with mocked retrieval and LLM."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "OPENROUTER_API_KEY", "test-key")
    return TestClient(main.app)


def _fake_llm(answer: str):
    class _Resp:
        choices = [SimpleNamespace(message=SimpleNamespace(content=answer))]

    class _Chat:
        class completions:
            @staticmethod
            def create(**_kwargs):
                return _Resp()

    return SimpleNamespace(chat=_Chat())


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_ask_returns_answer_and_sources(client, monkeypatch):
    fake_threads = [
        {
            "document": "Subject: Project kickoff\nFrom: Alice\n\nLet's start next week.",
            "metadata": {
                "subject": "Project kickoff",
                "first_sender": "Alice <alice@example.com>",
                "first_date": "2024-01-01T09:00:00+00:00",
                "participants": "Alice, Bob",
                "message_count": 2,
                "messages_json": json.dumps(
                    [
                        {
                            "sender": "Alice <alice@example.com>",
                            "date": "2024-01-01T09:00:00+00:00",
                            "to": "Bob",
                            "cc": "",
                            "body": "Let's start next week.",
                        }
                    ]
                ),
            },
            "score": 0.87,
        }
    ]
    monkeypatch.setattr(main, "collection_exists", lambda: True)
    monkeypatch.setattr(main, "retrieve", lambda q, n_results: fake_threads)
    monkeypatch.setattr(main, "get_llm", lambda: _fake_llm("The project kicks off next week."))

    r = client.post("/ask", json={"question": "When does the project start?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "The project kicks off next week."
    assert len(body["sources"]) == 1
    src = body["sources"][0]
    assert src["subject"] == "Project kickoff"
    assert src["sender"] == "Alice <alice@example.com>"
    assert src["score"] == 0.87
    assert src["message_count"] == 2
    assert len(src["messages"]) == 1
    assert src["messages"][0]["body"] == "Let's start next week."


def test_ask_empty_when_no_relevant_threads(client, monkeypatch):
    monkeypatch.setattr(main, "collection_exists", lambda: True)
    monkeypatch.setattr(main, "retrieve", lambda q, n_results: [])
    # LLM should not be called — but provide a stub anyway just in case.
    monkeypatch.setattr(main, "get_llm", lambda: _fake_llm("should not be used"))

    r = client.post("/ask", json={"question": "Anything?"})
    assert r.status_code == 200
    body = r.json()
    assert body["sources"] == []
    assert "No relevant" in body["answer"]


def test_ask_404_when_collection_missing(client, monkeypatch):
    monkeypatch.setattr(main, "collection_exists", lambda: False)
    r = client.post("/ask", json={"question": "X"})
    assert r.status_code == 404
    assert "index" in r.json()["detail"].lower()


def test_ask_500_when_api_key_missing(monkeypatch):
    monkeypatch.setattr(main, "OPENROUTER_API_KEY", "")
    client = TestClient(main.app)
    r = client.post("/ask", json={"question": "X"})
    assert r.status_code == 500
    assert "OPENROUTER_API_KEY" in r.json()["detail"]


def test_ask_502_when_llm_fails(client, monkeypatch):
    fake_threads = [
        {
            "document": "doc",
            "metadata": {
                "subject": "s",
                "first_sender": "x",
                "first_date": "2024-01-01T00:00:00",
                "participants": "",
                "message_count": 1,
                "messages_json": "[]",
            },
            "score": 0.5,
        }
    ]
    monkeypatch.setattr(main, "collection_exists", lambda: True)
    monkeypatch.setattr(main, "retrieve", lambda q, n_results: fake_threads)

    class _Boom:
        class chat:
            class completions:
                @staticmethod
                def create(**_kwargs):
                    raise RuntimeError("upstream down")

    monkeypatch.setattr(main, "get_llm", lambda: _Boom())

    r = client.post("/ask", json={"question": "X"})
    assert r.status_code == 502
    assert "LLM error" in r.json()["detail"]


def test_ingest_endpoint_invokes_ingest(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "ingest",
        lambda path, force: {
            "reindexed": True,
            "threads_count": 7,
            "message": "Successfully indexed 7 threads",
            "checksum": "abc123",
        },
    )
    r = client.post("/ingest", json={"force": False})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["reindexed"] is True
    assert body["threads_count"] == 7


def test_ingest_endpoint_surfaces_errors(client, monkeypatch):
    def boom(_path, force):
        raise RuntimeError("mbox missing")

    monkeypatch.setattr(main, "ingest", boom)
    r = client.post("/ingest", json={"force": False})
    assert r.status_code == 500
    assert "mbox missing" in r.json()["detail"]


def test_status_endpoint(client, monkeypatch):
    monkeypatch.setattr(
        main,
        "get_collection_stats",
        lambda: {"exists": True, "count": 10, "checksum": "xyz"},
    )
    r = client.get("/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["indexed"] is True
    assert body["threads_count"] == 10
    assert body["needs_indexing"] is False
