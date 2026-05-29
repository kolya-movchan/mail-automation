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
MBOX_PATH=../data/sample.mbox
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
data/sample.mbox
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

### Python + FastAPI (backend)

Python has the best ecosystem for mbox parsing (`mailbox` stdlib), embeddings (`sentence-transformers`), and vector databases. FastAPI provides async request handling, automatic OpenAPI docs, and Pydantic validation with minimal boilerplate. Alternatives considered: Flask (synchronous, more boilerplate), Go (fewer ML libraries).

### Next.js + Tailwind CSS (frontend)

React with the App Router gives a production-ready setup with TypeScript, hot reload, and zero config. Tailwind makes UI iteration fast without a separate stylesheet. Alternatives: plain HTML/JS (no type safety), Vue (smaller ecosystem for this use case).

### ChromaDB (vector database)

ChromaDB runs fully locally with no Docker or external services required, making it ideal for a demo. It supports persistent storage and cosine similarity search out of the box. Alternatives considered: Pinecone (cloud-only), pgvector (requires PostgreSQL), Weaviate (Docker required), FAISS (no persistence built-in).

### sentence-transformers / all-MiniLM-L6-v2 (embeddings)

Free, runs locally with no API key, fast inference on CPU, and produces high-quality semantic embeddings. `all-MiniLM-L6-v2` is a widely-used model that balances speed and quality for English text. Alternatives: OpenAI `text-embedding-3-small` (costs money, requires API key), Cohere embeddings (same).

### OpenRouter (LLM for Q&A)

OpenRouter provides a single OpenAI-compatible API that routes to any provider (Anthropic, OpenAI, Google, Mistral, Meta, etc.). This means one API key works across all providers and models can be swapped with a single config change. Defaults to `meta-llama/llama-3.1-8b-instruct` — a fully open-source model (Meta, Apache 2.0 license) that excels at instruction following and reading provided context, making it ideal for RAG Q&A. It is also available on the OpenRouter free tier. Alternatives: `mistralai/mistral-7b-instruct` (similar quality/speed), `anthropic/claude-3-haiku` (proprietary), direct provider SDKs (vendor lock-in).

### RAG (Retrieval-Augmented Generation)

The query is embedded and compared against all stored thread embeddings. The top-5 most semantically similar threads are injected as context into the LLM prompt. This approach scales to large archives without hitting token limits, and ensures answers are grounded in the actual emails. Alternatives: full context injection (hits token limits at scale), fine-tuning (expensive, overkill for Q&A).

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
│   ├── sample.mbox      # Gmail Takeout export
│   └── chroma/          # ChromaDB persistent storage (created by make ingest)
├── Makefile
└── README.md
```
