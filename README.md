# Email Knowledge Base

An AI-powered Q&A system over Gmail exports. Ask natural-language questions about your email archive and get accurate answers with source references.

## ✨ Live Demo

**👉 [Try it here](https://mail-knowledge-base-production.up.railway.app/)** — No setup needed, just ask questions about the sample email archive.

---

## 🚀 Quick Start

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
CHROMA_DATA_DIR=./data/chroma
MBOX_PATH=./data/sample-1.mbox
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

## 🏗️ Architecture

```
backend/data/sample-1.mbox
      │
      ▼
backend/ingest.py          ← parse mbox → group threads → embed → ChromaDB
      │
      ▼
backend/data/chroma/       ← persistent vector store (local)
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

## 🔧 Technology Choices

**ChromaDB** — needed vector search for semantic Q&A (not just keyword matching). Chose it because it's embedded (no Docker/server), pip-installable, and persists locally. Beats pgvector (needs Postgres), Weaviate/Qdrant (need containers), Pinecone (cloud-only). Embedding whole threads (via `X-GM-THRID` header) instead of individual messages so results are complete conversations.

**Embeddings** — `all-MiniLM-L6-v2` via sentence-transformers. Free, runs on CPU, fast, good MTEB scores. Skipped OpenAI embeddings to avoid extra API dependency for ~50 threads.

**LLM** — OpenRouter as gateway (one key, works with any provider). Default to Llama 3.1 8B (Apache-2.0, free tier, good at RAG). Avoided LangChain/LlamaIndex (overkill for basic RAG).

**RAG flow** — embed query → top 5 similar threads → inject as context → LLM answers. Added 0.30 cosine similarity threshold to filter junk results. Scales better than dumping all emails in prompt.

**Frontend** — Next.js 16 + React 19 + Tailwind v4. Web UI is easiest to demo. Single client component posting to FastAPI. Tailwind for inline styles and color-coded relevance badges.

**Backend** — Python + FastAPI. Python has stdlib `mailbox`, sentence-transformers, ChromaDB. FastAPI for quick API setup with Pydantic validation and auto docs. Using `email.policy.default` for proper Unicode handling (not `compat32`).

**Tooling** — `uv` for fast Python deps (10x faster than pip), Make for clean task interface (`make setup`, `make ingest`, etc.).

---

## ✅ Testing & CI/CD

The brief lists automated tests and CI/CD as out of scope — both are added here as extra mile.

### Tests

The backend has a pytest suite covering ingestion parsing, retrieval filtering, and every FastAPI endpoint (happy path + error paths). The LLM and vector store are stubbed so the tests are fast, deterministic, and need no network or API key.

```bash
make test
```

What's covered:

- **`tests/test_ingest.py`** — mbox parsing (headers, MIME-encoded subjects, Unicode bodies, ISO date normalization), thread grouping by `X-GM-THRID`, fallback to subject-based grouping, chronological message ordering.
- **`tests/test_retriever.py`** — cosine-similarity score filtering, the `min_score` floor, empty-result behavior. Uses a fake Chroma collection so no model download.
- **`tests/test_api.py`** — `/health`, `/ask` (200 / 404 / 500 / 502), `/ingest` (200 / 500), source-reference shape, error surfacing from upstream LLM failures.

### CI

`.github/workflows/ci.yml` runs on every push and PR to `master`/`main`:

- **Backend job** — installs deps with `uv`, runs the pytest suite.
- **Frontend job** — `npm ci`, `npm run lint`, `npm run build` (the build step type-checks as well).

### CD

Railway is wired to auto-deploy on push to the default branch, so continuous deployment is covered there. The GitHub Actions workflow above adds the missing CI half — gating PRs on tests and lint before they land.

---

## 📁 Project Structure

```
mail-automation/
├── .github/workflows/
│   └── ci.yml           # Backend pytest + frontend lint/build on every PR
├── backend/
│   ├── main.py          # FastAPI app — /ingest and /ask endpoints
│   ├── ingest.py        # mbox parsing, thread grouping, embedding, ChromaDB storage
│   ├── retriever.py     # vector similarity retrieval
│   ├── tests/           # pytest suite (ingest, retriever, API)
│   ├── data/
│   │   ├── sample-1.mbox  # Gmail Takeout export
│   │   └── chroma/      # ChromaDB persistent storage (created by make ingest)
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   ├── .env.example
│   └── .venv/           # Python virtual environment (created by make setup)
├── frontend/
│   ├── app/
│   │   ├── page.tsx     # Main Q&A page (Client Component)
│   │   └── layout.tsx
│   └── package.json
├── Makefile
└── README.md
```
