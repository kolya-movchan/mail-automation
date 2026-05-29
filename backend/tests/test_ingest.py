"""Unit tests for mbox parsing and thread grouping."""

from __future__ import annotations

from pathlib import Path

from ingest import decode_str, group_into_threads, parse_mbox


def test_decode_str_handles_none_and_empty():
    assert decode_str(None) == ""
    assert decode_str("") == ""


def test_decode_str_plain():
    assert decode_str("Hello") == "Hello"


def test_decode_str_mime_encoded():
    # =?utf-8?B?...?= encoded "Café"
    assert decode_str("=?utf-8?B?Q2Fmw6k=?=") == "Café"


def test_parse_mbox_extracts_all_messages(sample_mbox_path: Path):
    emails = parse_mbox(str(sample_mbox_path))
    assert len(emails) == 3
    senders = {e["from"] for e in emails}
    assert "Alice <alice@example.com>" in senders
    assert "Bob <bob@example.com>" in senders
    assert "Dave <dave@example.com>" in senders


def test_parse_mbox_preserves_headers(sample_mbox_path: Path):
    emails = parse_mbox(str(sample_mbox_path))
    first = next(e for e in emails if e["message_id"] == "<msg-1@example.com>")
    assert first["subject"] == "Project kickoff"
    assert first["to"] == "Bob <bob@example.com>"
    assert first["cc"] == "Carol <carol@example.com>"
    assert first["x_gm_thrid"] == "1000000000000000001"
    assert "stack" in first["body"]


def test_parse_mbox_preserves_in_reply_to(sample_mbox_path: Path):
    emails = parse_mbox(str(sample_mbox_path))
    reply = next(e for e in emails if e["message_id"] == "<msg-2@example.com>")
    assert reply["in_reply_to"] == "<msg-1@example.com>"
    assert reply["references"] == "<msg-1@example.com>"


def test_parse_mbox_date_normalized_to_iso(sample_mbox_path: Path):
    emails = parse_mbox(str(sample_mbox_path))
    first = next(e for e in emails if e["message_id"] == "<msg-1@example.com>")
    # parsedate_to_datetime → isoformat
    assert first["date"].startswith("2024-01-01T09:00:00")


def test_group_into_threads_uses_x_gm_thrid(sample_mbox_path: Path):
    emails = parse_mbox(str(sample_mbox_path))
    threads = group_into_threads(emails)

    # Two threads: kickoff (2 msgs) + lunch (1 msg)
    assert len(threads) == 2

    kickoff = next(t for t in threads if "kickoff" in t["subject"].lower())
    assert kickoff["message_count"] == 2
    assert "Alice <alice@example.com>" in kickoff["participants"]
    assert "Bob <bob@example.com>" in kickoff["participants"]

    lunch = next(t for t in threads if "lunch" in t["subject"].lower())
    assert lunch["message_count"] == 1


def test_group_into_threads_orders_messages_by_date(sample_mbox_path: Path):
    emails = parse_mbox(str(sample_mbox_path))
    threads = group_into_threads(emails)
    kickoff = next(t for t in threads if "kickoff" in t["subject"].lower())
    assert kickoff["messages"][0]["from"] == "Alice <alice@example.com>"
    assert kickoff["messages"][1]["from"] == "Bob <bob@example.com>"
    assert kickoff["first_sender"] == "Alice <alice@example.com>"


def test_group_into_threads_falls_back_to_subject_when_no_thrid():
    emails = [
        {
            "id": "a",
            "subject": "Quarterly report",
            "from": "alice@example.com",
            "to": "",
            "cc": "",
            "date": "2024-01-01T09:00:00",
            "body": "Here is Q1",
            "message_id": "<a>",
            "in_reply_to": "",
            "references": "",
            "x_gm_thrid": "",
        },
        {
            "id": "b",
            "subject": "Re: Quarterly report",
            "from": "bob@example.com",
            "to": "",
            "cc": "",
            "date": "2024-01-02T09:00:00",
            "body": "Thanks!",
            "message_id": "<b>",
            "in_reply_to": "<a>",
            "references": "<a>",
            "x_gm_thrid": "",
        },
    ]
    threads = group_into_threads(emails)
    assert len(threads) == 1
    assert threads[0]["message_count"] == 2
