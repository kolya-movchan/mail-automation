.PHONY: setup install-backend install-backend-dev install-frontend ingest backend frontend dev test help

help:
	@echo "Usage:"
	@echo "  make setup       - Install all dependencies"
	@echo "  make ingest      - Parse mbox and load into ChromaDB"
	@echo "  make backend     - Start FastAPI server (port 8000)"
	@echo "  make frontend    - Start Next.js dev server (port 3000)"
	@echo "  make dev         - Start both servers (requires two terminals)"
	@echo "  make test        - Run backend tests (pytest)"

setup: install-backend install-frontend

install-backend:
	cd backend && uv venv .venv --python 3.11 && uv pip install -r requirements.txt

install-backend-dev:
	cd backend && uv venv .venv --python 3.11 && uv pip install -r requirements-dev.txt

test: install-backend-dev
	cd backend && .venv/bin/pytest

install-frontend:
	cd frontend && npm install

ingest:
	cd backend && .venv/bin/python ingest.py

backend:
	cd backend && .venv/bin/uvicorn main:app --reload --port 8000

frontend:
	cd frontend && npm run dev
