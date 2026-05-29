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

The test brief requires that every tool, library, and service is justified. This section is organized by the categories the brief calls out — **Storage**, **AI model**, **Interface** — followed by supporting choices (language, framework, parsing, packaging).

### Storage

#### ChromaDB — vector database

**Why:** The task is semantic Q&A over email threads, where users ask things like *"why did the API gateway return 503s?"* — the relevant thread doesn't necessarily share keywords with the question. That rules out plain keyword search (SQLite FTS, Postgres FTS) and points to vector similarity. ChromaDB runs **fully embedded in-process** with a single `pip install`, persists to a local directory, and supports cosine distance via `hnsw:space: "cosine"` — exactly what a self-contained demo needs.

**Alternatives considered:**
- **pgvector** — requires running PostgreSQL; overkill for a single-process demo.
- **Weaviate / Qdrant** — require Docker; adds setup friction.
- **Pinecone** — cloud-only, requires an API key and account, and stores data off-machine.
- **FAISS** — fast but has no built-in persistence layer or metadata storage; we'd have to build the metadata sidecar ourselves.
- **SQLite FTS5** — pure keyword search; would miss semantically related threads.

#### Storage schema — one embedding per thread

Each Gmail thread (not individual message) is embedded as a single vector. Messages are grouped first by `X-GM-THRID` (the authoritative Gmail thread identifier), then by normalized subject line for any messages missing that header. The combined body of all messages in the thread is what gets embedded, with metadata (subject, first sender, dates, participants, message count) attached for display in source cards. This means a single similarity match returns a complete, contextually whole conversation — not a fragment.

### AI Model

#### sentence-transformers + `all-MiniLM-L6-v2` — embeddings

**Why:** Embeddings are computed once at ingest time and again per query, so cost matters. `all-MiniLM-L6-v2` is **free, runs on CPU**, produces 384-dim vectors in milliseconds, and consistently ranks among the top general-purpose English models on the [MTEB benchmark](https://huggingface.co/spaces/mteb/leaderboard) for its size. No API key, no rate limits, no cost.

**Alternatives considered:**
- **OpenAI `text-embedding-3-small`** — higher quality but costs money and requires an API key; quality gain doesn't justify the dependency for ~50 threads.
- **Cohere embeddings** — same trade-off as OpenAI.
- **`all-mpnet-base-v2`** — higher quality but ~3× slower; not worth it at this corpus size.

#### OpenRouter — LLM gateway

**Why:** OpenRouter is a single **OpenAI-compatible** endpoint that proxies to virtually every major model provider (Anthropic, OpenAI, Google, Meta, Mistral, etc.). One API key, one SDK (`openai` Python client pointed at OpenRouter's base URL), and the model is swappable via a single env var. This is exactly the flexibility a reviewer benefits from — they can try the system with a free open-source model without signing up for proprietary providers.

The default is `meta-llama/llama-3.1-8b-instruct` — Apache-2.0-licensed, available on OpenRouter's free tier, and well-suited to grounded-answer RAG where the model must read provided context rather than rely on its own knowledge.

**Alternatives considered:**
- **Anthropic / OpenAI / Google SDKs directly** — vendor lock-in; switching models means rewriting client code.
- **Local LLM via Ollama** — adds significant setup (model download, separate server process); excessive for a 3-hour task.
- **LangChain / LlamaIndex abstractions** — heavyweight framework dependencies for what is ~30 lines of HTTP-and-prompt code.

#### RAG architecture (retrieval-augmented generation)

**Why:** Stuffing all email threads directly into a single prompt would exceed context windows on larger archives and is wasteful on tokens. RAG instead embeds the query, retrieves the top-K (K=5) most similar threads from ChromaDB, and only injects those as context. This **scales to any archive size** while keeping answers grounded in actual emails (and lets us surface the same retrieved threads as source citations in the UI).

A relevance threshold (`MIN_RELEVANCE = 0.30` cosine similarity) filters out unrelated threads that happened to be in the top-K but aren't actually about the question — preventing the noisy "we matched 5 things even though only 1 was relevant" problem.

**Alternatives considered:**
- **Full-context injection** — works for tiny corpora but hits token limits and costs more per query.
- **Fine-tuning a model on the archive** — slow, expensive, and the result can't cite sources.
- **Reranking with a cross-encoder** — would improve retrieval precision but adds another model and noticeable latency; not justified at 50 threads.

### Interface

#### Next.js 16 (App Router) + React 19 — web UI

**Why:** The brief allows web/CLI/Slack. A web UI is the most reviewer-friendly — no terminal-pasting, you can see the answer card and source citations side-by-side. Next.js with the App Router gives **TypeScript, hot reload, and production-ready defaults out of the box** with `create-next-app`. A single client component (`app/page.tsx`) handles the entire interaction; we don't need server actions, route handlers, or RSC for a simple "POST to FastAPI" flow.

**Alternatives considered:**
- **CLI** — fastest to build but harder for a reviewer to demo and inspect.
- **Plain HTML + vanilla JS** — no type safety, no component model; UI iteration is slower.
- **Vite + React** — fine choice; Next.js was picked because the App Router scaffolding is more turnkey.
- **Streamlit / Gradio** — fast for ML demos but visually generic and hard to customize.

#### Tailwind CSS v4 — styling

**Why:** Tailwind keeps styles co-located with components, avoids a separate CSS file to maintain, and v4's Lightning CSS engine compiles instantly. The relevance-tier color coding (emerald/amber/slate score badges) is trivial to express inline.

**Alternatives considered:**
- **CSS modules / vanilla CSS** — more files, slower iteration.
- **shadcn/ui** — high-quality components, but adds dependencies and is overkill for this surface area.
- **Material UI / Chakra** — opinionated theming we'd have to override.

### Supporting Choices

#### Python — language

**Why:** Python has the strongest ecosystem for the three things this app does: **mbox parsing** (`mailbox` is stdlib), **embeddings** (`sentence-transformers`), and **vector DBs** (ChromaDB's primary client is Python). Doing this in JS would mean shelling out to a Python process for embeddings anyway.

**Alternatives considered:**
- **Node.js** — would require `@xenova/transformers` (slower than the Python original) or an external embedding API.
- **Go** — minimal ML library support; would force an external embeddings service.

#### FastAPI — backend framework

**Why:** Two endpoints (`/ingest`, `/ask`), Pydantic request/response validation, automatic OpenAPI docs at `/docs`, and async-ready — all with ~10 lines of setup. Plays well with the OpenAI client and `sentence-transformers`.

**Alternatives considered:**
- **Flask** — would need separate libraries for validation and OpenAPI docs.
- **Django** — far too heavy for two endpoints.
- **Starlette directly** — FastAPI is a thin wrapper that adds validation we want.

#### Python `mailbox` + `email.policy.default` — mbox parsing

**Why:** `mailbox` is stdlib and handles the mbox format natively. The default `compat32` policy decodes headers as ASCII (mangling UTF-8 characters like `—` into `���`), so we explicitly use **`email.policy.default`** when constructing the mailbox, which decodes headers correctly as Unicode.

**Alternatives considered:**
- **`mail-parser` (PyPI)** — wrapper around `email`; doesn't solve anything stdlib already handles.
- **Hand-rolled regex parsing** — fragile against real-world mbox quirks (MIME-encoded headers, multipart bodies, charset variations).

#### OpenAI Python SDK — LLM client

**Why:** OpenRouter exposes an OpenAI-compatible API, so we can use the official `openai` SDK by just overriding `base_url`. Zero custom HTTP code.

**Alternatives considered:**
- **`httpx` directly** — would mean writing our own retry/streaming logic.
- **LangChain `ChatOpenAI`** — pulls in a heavy framework for one chat call.

#### `uv` — Python package manager

**Why:** ~10–100× faster installs than `pip` for this dependency set (`sentence-transformers` and `chromadb` have large dep trees), and creates a lockable virtualenv in one command. Makes the `make setup` one-liner actually fast.

**Alternatives considered:**
- **`pip` + `venv`** — works but materially slower for first-time setup.
- **`poetry`** — heavier; project metadata in `pyproject.toml` not needed for a demo.

#### Make — task runner

**Why:** Standard, no extra install, and gives reviewers a single discoverable interface (`make setup`, `make ingest`, `make backend`, `make frontend`). Satisfies the brief's "one-command setup is ideal."

**Alternatives considered:**
- **Shell scripts** — would scatter across multiple files.
- **`just`** — nicer syntax but adds an install step.
- **npm scripts only** — can't naturally coordinate backend + frontend.

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
