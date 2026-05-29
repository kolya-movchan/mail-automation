# Email Knowledge Base

An AI-powered Q&A system over Gmail exports. Ask natural-language questions about your email archive and get accurate answers with source references.

## Quick Start

### 1. Prerequisites

- Python 3.11+ and `uv` (`pip install uv` or `brew install uv`)
- Node.js 18+
- An [OpenRouter](https://openrouter.ai) API key

### 2. Install dependencies

```bash
make setup
```

### 3. Configure environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set your OpenRouter API key:

```env
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct   # or any OpenRouter model
CHROMA_DATA_DIR=../data/chroma
MBOX_PATH=../data/sample-1.mbox
```

### 4. Ingest emails

```bash
make ingest
```

This parses the `.mbox` file, groups messages into threads, embeds them locally, and stores them in ChromaDB.

### 5. Run the app

Open two terminals:

```bash
# Terminal 1 — backend API
make backend

# Terminal 2 — frontend UI
make frontend
```

Then open [http://localhost:3000](http://localhost:3000).

You can also click **"Ingest emails"** in the UI to re-run ingestion without the terminal.

---

## Architecture

```
data/sample-1.mbox
      │
      ▼
backend/ingest.py          ← parse mbox → group threads → embed → ChromaDB
      │
      ▼
data/chroma/               ← persistent vector store (local)
      │
      ▼
backend/main.py (FastAPI)
  POST /ingest             ← triggers ingestion
  POST /ask                ← embed query → retrieve top-5 → prompt LLM → answer + sources
      │
      ▼
frontend/ (Next.js)        ← question input → answer card → source thread cards
```

---

## Technology Choices

Here's how I picked the stack for this. The brief asked me to justify every choice, so I'm walking through the main decisions and what I was thinking.

### Storage — ChromaDB for vector search

The whole point here is semantic Q&A over emails. Someone asks "why did the API gateway return 503s?" and the answer might be in a thread that never mentions those exact words. Keyword search (SQLite FTS, Postgres full-text, whatever) wouldn't cut it. I needed vector similarity search.

ChromaDB was perfect because it's just `pip install chromadb` and it runs embedded — no separate server process, no Docker, nothing. It persists to a local directory and supports cosine distance out of the box. For a self-contained demo that needs to run on anyone's machine, that's exactly what I wanted. I looked at pgvector but that means running Postgres, which felt like overkill. Weaviate and Qdrant need Docker containers. Pinecone is cloud-only and I wanted everything local. FAISS is fast but doesn't have built-in persistence or metadata storage, so I'd have to build that myself.

I went with one embedding per thread instead of per message. Each thread gets grouped by Gmail's `X-GM-THRID` header (or by normalized subject line if that's missing), then all the messages in that thread get combined and embedded as one vector. Metadata like subject, sender, dates, participant list, etc. gets attached for display. That way when you search, you get back a complete conversation, not random fragments.

### Embeddings — sentence-transformers with all-MiniLM-L6-v2

For embeddings I picked `all-MiniLM-L6-v2` via the `sentence-transformers` library. It's free, runs on CPU, generates 384-dim vectors in milliseconds, and scores really well on the MTEB benchmark for its size. No API key, no rate limits, no per-query cost. Since embeddings happen at ingest time and then again for every query, keeping this local and fast mattered.

I thought about OpenAI's `text-embedding-3-small` — it's higher quality — but for ~50 email threads the quality gain didn't justify adding another API dependency.

### LLM — OpenRouter for flexibility

I went with OpenRouter as the LLM gateway. It's one API key, OpenAI-compatible, and proxies to basically every major provider (Anthropic, OpenAI, Google, Meta, Mistral, you name it). That meant I could use the official OpenAI Python SDK and just point `base_url` at OpenRouter. 

I set the default to `meta-llama/llama-3.1-8b-instruct` because it's Apache-2.0 licensed, available on OpenRouter's free tier, and it's good at reading provided context (which is what RAG needs). I didn't want to lock this to Claude or GPT because that adds vendor lock-in and costs money. LangChain and LlamaIndex felt like overkill for what's basically 30 lines of prompt-and-HTTP code.

### RAG — retrieval-augmented generation

I structured this as a classic RAG setup: embed the user's query, pull the top 5 most similar threads from ChromaDB, inject just those as context, and ask the LLM to answer from that. This scales to any archive size (you're not dumping thousands of emails into the prompt), keeps answers grounded in real data, and lets me show the same retrieved threads as source cards in the UI.

I added a relevance threshold (0.30 cosine similarity) to filter out threads that were in the top 5 but aren't actually relevant. That prevents the "we returned 5 matches even though 4 were junk" problem.

Dumping everything into the prompt would hit token limits on bigger archives and waste money. Fine-tuning a model on the emails would be slow, expensive, and wouldn't let me cite sources. A cross-encoder reranker would improve precision but adds another model and noticeable latency; didn't feel worth it for 50 threads.

### Frontend — Next.js + React

For the UI I went with Next.js 16 (App Router) and React 19. The brief said web, CLI, or Slack were all fine, but a web UI is way easier for someone reviewing this to try out. You just open a browser. Next.js gives TypeScript, hot reload, and solid defaults right out of `create-next-app`. The whole interaction is one client component in `app/page.tsx` that posts to FastAPI. I didn't need server components, route handlers, or any of that.

For styling I used Tailwind CSS v4. Keeps styles inline with components, no separate CSS file, and the new Lightning CSS engine is instant. The color-coded relevance badges (emerald/amber/slate) were trivial to add. I skipped CSS modules (more files to juggle), shadcn/ui (nice but overkill here), and Material UI / Chakra (too opinionated for what I needed).

### Backend — Python + FastAPI

Python was the obvious choice for the backend. The stdlib has `mailbox` for mbox parsing, `sentence-transformers` is Python-first, and ChromaDB's main client is Python. If I'd done this in Node I'd have to use `@xenova/transformers` (which is slower) or call out to an external embedding API. Go doesn't have the ML ecosystem. Hower, I am Node-first person 🥲

FastAPI made sense for the web framework. Two endpoints (`/ingest` and `/ask`), Pydantic request/response validation, automatic OpenAPI docs at `/docs`, and it's async-ready. Took like 10 lines to set up. Flask would've needed extra libraries for validation and docs. Django is way too heavy for two endpoints. Starlette directly is fine but FastAPI is just a thin wrapper that adds stuff I wanted anyway.

For mbox parsing I used Python's stdlib `mailbox` module with `email.policy.default`. The default policy (`compat32`) decodes headers as ASCII and mangles UTF-8 characters into gibberish. The `default` policy handles Unicode correctly. I looked at `mail-parser` on PyPI but it's just a wrapper around `email` and doesn't add anything I needed. Hand-rolling regex parsing for mbox files sounded like a nightmare (MIME-encoded headers, multipart bodies, charset hell).

Since OpenRouter is OpenAI-compatible, I just used the official OpenAI Python SDK and overrode `base_url`. No custom HTTP code, no reinventing retry logic.

### Tooling — uv + Make

I went with `uv` as the Python package manager because it's 10+ faster than `pip` for this dependency set (`sentence-transformers` and `chromadb` have massive dep trees). It creates a lockable virtualenv in one command, which makes `make setup` actually fast. `poetry` would've worked but felt heavier than I needed for a demo.

For task running I used Make. It's standard, no extra install, and gives reviewers a clean interface (`make setup`, `make ingest`, `make backend`, `make frontend`). The brief wanted "one-command setup" and Make delivers that. I could've written shell scripts but then they'd be scattered across files. `just` has nicer syntax but adds an install step. npm scripts alone can't coordinate backend + frontend cleanly.

---

## Project Structure

```
mail-automation/
├── backend/
│   ├── main.py          # FastAPI app — /ingest and /ask endpoints
│   ├── ingest.py        # mbox parsing, thread grouping, embedding, ChromaDB storage
│   ├── retriever.py     # vector similarity retrieval
│   ├── requirements.txt
│   ├── .env.example
│   └── .venv/           # Python virtual environment (created by make setup)
├── frontend/
│   ├── app/
│   │   ├── page.tsx     # Main Q&A page (Client Component)
│   │   └── layout.tsx
│   └── package.json
├── data/
│   ├── sample-1.mbox      # Gmail Takeout export
│   └── chroma/          # ChromaDB persistent storage (created by make ingest)
├── Makefile
└── README.md
```
