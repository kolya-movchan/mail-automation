"""Parse .mbox file, embed each email thread, and store in ChromaDB."""

import json
import mailbox
import os
import re
import sys
from email import message_from_binary_file, policy
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime

import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()

CHROMA_DATA_DIR = os.getenv("CHROMA_DATA_DIR", "../data/chroma")
MBOX_PATH = os.getenv("MBOX_PATH", "../data/sample-1.mbox")
COLLECTION_NAME = "email_threads"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


def decode_str(value: str | None) -> str:
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def get_body(msg) -> str:
    """Extract plain-text body from a message, handling multipart."""
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and not part.get_filename():
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    try:
                        parts.append(payload.decode(charset, errors="replace"))
                    except Exception:
                        parts.append(payload.decode("utf-8", errors="replace"))
        return "\n".join(parts)
    payload = msg.get_payload(decode=True)
    if payload:
        charset = msg.get_content_charset() or "utf-8"
        try:
            return payload.decode(charset, errors="replace")
        except Exception:
            return payload.decode("utf-8", errors="replace")
    return ""


def parse_mbox(path: str) -> list[dict]:
    """Parse mbox into a list of email dicts grouped by thread."""
    mbox = mailbox.mbox(
        path,
        factory=lambda f: message_from_binary_file(f, policy=policy.default),
    )
    emails = []
    for key, msg in mbox.items():
        message_id = (msg.get("Message-ID") or "").strip()
        in_reply_to = (msg.get("In-Reply-To") or "").strip()
        references = (msg.get("References") or "").strip()
        x_gm_thrid = (msg.get("X-GM-THRID") or "").strip()

        try:
            date_str = msg.get("Date", "")
            date = parsedate_to_datetime(date_str).isoformat() if date_str else ""
        except Exception:
            date = msg.get("Date", "")

        emails.append(
            {
                "id": message_id or f"msg-{key}",
                "subject": decode_str(msg.get("Subject", "(no subject)")),
                "from": decode_str(msg.get("From", "")),
                "to": decode_str(msg.get("To", "")),
                "cc": decode_str(msg.get("Cc", "")),
                "date": date,
                "body": get_body(msg),
                "message_id": message_id,
                "in_reply_to": in_reply_to,
                "references": references,
                "x_gm_thrid": x_gm_thrid,
            }
        )
    return emails


def group_into_threads(emails: list[dict]) -> list[dict]:
    """Group individual emails into threads using X-GM-THRID or References."""
    # First pass: group by X-GM-THRID if available
    gm_threads: dict[str, list[dict]] = {}
    no_thrid = []

    for email in emails:
        thrid = email["x_gm_thrid"]
        if thrid:
            gm_threads.setdefault(thrid, []).append(email)
        else:
            no_thrid.append(email)

    # For emails without X-GM-THRID, group by subject (normalized)
    subject_threads: dict[str, list[dict]] = {}
    for email in no_thrid:
        normalized = re.sub(r"^(re|fwd|fw|sv|aw):\s*", "", email["subject"].lower()).strip()
        subject_threads.setdefault(normalized, []).append(email)

    threads = []

    def make_thread(msgs: list[dict], thread_id: str) -> dict:
        msgs_sorted = sorted(msgs, key=lambda m: m["date"])
        first = msgs_sorted[0]
        all_senders = list({m["from"] for m in msgs_sorted if m["from"]})
        combined_body = "\n\n---\n\n".join(
            f"From: {m['from']}\nDate: {m['date']}\n\n{m['body'][:2000]}"
            for m in msgs_sorted
        )
        return {
            "thread_id": thread_id,
            "subject": first["subject"],
            "participants": all_senders,
            "first_sender": first["from"],
            "first_date": first["date"],
            "last_date": msgs_sorted[-1]["date"],
            "message_count": len(msgs_sorted),
            "combined_body": combined_body[:8000],
            "messages": msgs_sorted,
        }

    for thrid, msgs in gm_threads.items():
        threads.append(make_thread(msgs, thrid))

    for subject, msgs in subject_threads.items():
        thread_id = f"subj-{re.sub(r'[^a-z0-9]', '-', subject)[:40]}"
        threads.append(make_thread(msgs, thread_id))

    return threads


def ingest(mbox_path: str = MBOX_PATH, chroma_dir: str = CHROMA_DATA_DIR) -> int:
    print(f"Parsing {mbox_path}...")
    emails = parse_mbox(mbox_path)
    print(f"  Found {len(emails)} individual messages")

    threads = group_into_threads(emails)
    print(f"  Grouped into {len(threads)} threads")

    print(f"Loading embedding model ({EMBEDDING_MODEL})...")
    model = SentenceTransformer(EMBEDDING_MODEL)

    print(f"Connecting to ChromaDB at {chroma_dir}...")
    client = chromadb.PersistentClient(path=chroma_dir, settings=Settings(anonymized_telemetry=False))

    # Drop and recreate collection for a clean ingest
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )

    texts = []
    metadatas = []
    ids = []

    for i, thread in enumerate(threads):
        text = f"Subject: {thread['subject']}\nFrom: {thread['first_sender']}\nDate: {thread['first_date']}\n\n{thread['combined_body']}"
        texts.append(text)
        messages_payload = [
            {
                "sender": m["from"],
                "date": m["date"],
                "to": m["to"],
                "cc": m["cc"],
                "body": m["body"][:5000],
            }
            for m in thread["messages"]
        ]
        metadatas.append(
            {
                "thread_id": thread["thread_id"],
                "subject": thread["subject"],
                "first_sender": thread["first_sender"],
                "first_date": thread["first_date"],
                "last_date": thread["last_date"],
                "message_count": thread["message_count"],
                "participants": ", ".join(thread["participants"][:5]),
                "messages_json": json.dumps(messages_payload),
            }
        )
        ids.append(f"thread-{i}")

    print(f"Embedding {len(texts)} threads...")
    embeddings = model.encode(texts, show_progress_bar=True).tolist()

    collection.add(documents=texts, embeddings=embeddings, metadatas=metadatas, ids=ids)
    print(f"Done! {len(threads)} threads stored in ChromaDB.")
    return len(threads)


if __name__ == "__main__":
    mbox = sys.argv[1] if len(sys.argv) > 1 else MBOX_PATH
    ingest(mbox)
