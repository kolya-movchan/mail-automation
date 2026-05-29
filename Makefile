.PHONY: setup install-backend install-frontend ingest backend frontend dev help

help:
	@echo "Usage:"
	@echo "  make setup       - Install all dependencies"
	@echo "  make ingest      - Parse mbox and load into ChromaDB"
	@echo "  make backend     - Start FastAPI server (port 8000)"
	@echo "  make frontend    - Start Next.js dev server (port 3000)"
	@echo "  make dev         - Start both servers (requires two terminals)"

setup: install-backend install-frontend

install-backend:
	cd backend && uv venv .venv --python 3.11 && uv pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

ingest:
	cd backend && .venv/bin/python ingest.py

backend:
	cd backend && .venv/bin/uvicorn main:app --reload --port 8000

frontend:
	cd frontend && npm run dev
