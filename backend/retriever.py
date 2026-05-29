"""Retrieve relevant email threads from ChromaDB for a given query."""

from __future__ import annotations

import os

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer

CHROMA_DATA_DIR = os.getenv("CHROMA_DATA_DIR", "../data/chroma")
COLLECTION_NAME = "email_threads"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

_model: SentenceTransformer | None = None
_client: chromadb.PersistentClient | None = None
_collection = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.PersistentClient(
            path=CHROMA_DATA_DIR, settings=Settings(anonymized_telemetry=False)
        )
        _collection = _client.get_collection(COLLECTION_NAME)
    return _collection


MIN_RELEVANCE = 0.30  # cosine similarity floor for "related" results


def retrieve(
    query: str,
    n_results: int = 5,
    min_score: float = MIN_RELEVANCE,
) -> list[dict]:
    """Return thread chunks relevant to the query.

    Always returns the top match (so the LLM has something to work with),
    plus any additional matches above `min_score`.
    """
    model = _get_model()
    collection = _get_collection()

    query_embedding = model.encode([query]).tolist()[0]
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, collection.count()),
        include=["documents", "metadatas", "distances"],
    )

    threads = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        threads.append(
            {
                "document": doc,
                "metadata": meta,
                "score": 1 - dist,  # cosine similarity when collection uses hnsw:space=cosine
            }
        )

    if not threads:
        return []
    relevant = [t for t in threads if t["score"] >= min_score]
    return relevant or threads[:1]
