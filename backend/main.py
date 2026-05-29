"""FastAPI backend: /ingest and /ask endpoints."""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

from ingest import ingest
from retriever import retrieve

app = FastAPI(title="Email Knowledge Base")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")
MBOX_PATH = os.getenv("MBOX_PATH", "../data/sample-1.mbox")

_llm_client: OpenAI | None = None


def get_llm() -> OpenAI:
    global _llm_client
    if _llm_client is None:
        _llm_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
    return _llm_client


class AskRequest(BaseModel):
    question: str
    n_results: int = 5


class Message(BaseModel):
    sender: str
    date: str
    to: str = ""
    cc: str = ""
    body: str


class Source(BaseModel):
    subject: str
    sender: str
    date: str
    participants: str
    message_count: int
    score: float
    messages: list[Message] = []


class AskResponse(BaseModel):
    answer: str
    sources: list[Source]


@app.post("/ingest")
def run_ingest():
    try:
        count = ingest(MBOX_PATH)
        return {"status": "ok", "threads_ingested": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    if not OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OPENROUTER_API_KEY not set")

    try:
        threads = retrieve(req.question, n_results=req.n_results)
    except ValueError:
        raise HTTPException(status_code=404, detail="No email data found. Run /ingest first.")

    if not threads:
        return AskResponse(
            answer="No relevant email threads were found in the archive for this question.",
            sources=[],
        )

    context = "\n\n".join(
        f"[Thread {i+1}]\n{t['document'][:1500]}" for i, t in enumerate(threads)
    )

    system_prompt = (
        "You are an AI assistant that answers questions about email threads. "
        "Use only the provided email context to answer. "
        "Be concise, accurate, and cite which thread your answer comes from."
    )
    user_prompt = (
        f"Email threads context:\n{context}\n\n"
        f"Question: {req.question}\n\n"
        "Answer the question based on the emails above. "
        "If the answer is not in the emails, say so."
    )

    try:
        response = get_llm().chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1024,
        )
        answer = response.choices[0].message.content or ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"LLM error: {e}")

    sources = []
    for t in threads:
        meta = t["metadata"]
        messages: list[Message] = []
        raw = meta.get("messages_json")
        if raw:
            try:
                for m in json.loads(raw):
                    messages.append(Message(**m))
            except (json.JSONDecodeError, TypeError):
                pass
        sources.append(
            Source(
                subject=meta.get("subject", ""),
                sender=meta.get("first_sender", ""),
                date=meta.get("first_date", ""),
                participants=meta.get("participants", ""),
                message_count=meta.get("message_count", 1),
                score=round(t["score"], 3),
                messages=messages,
            )
        )

    return AskResponse(answer=answer, sources=sources)


@app.get("/health")
def health():
    return {"status": "ok"}
