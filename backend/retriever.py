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


def _get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(
            path=CHROMA_DATA_DIR, settings=Settings(anonymized_telemetry=False)
        )
    return _client


def _get_collection():
    global _collection
    client = _get_client()
    try:
        _collection = client.get_collection(COLLECTION_NAME)
    except Exception:
        raise ValueError("Collection does not exist. Please ingest data first.")
    return _collection


def reset_collection_cache():
    """Reset cached collection reference (e.g., after reindexing)."""
    global _collection
    _collection = None


def collection_exists() -> bool:
    """Check if the collection exists in ChromaDB."""
    try:
        client = _get_client()
        collections = client.list_collections()
        return any(c.name == COLLECTION_NAME for c in collections)
    except Exception:
        return False


def get_collection_stats() -> dict:
    """Get collection statistics including count and checksum of data."""
    try:
        collection = _get_collection()
        count = collection.count()
        
        # Get a sample of documents to create a checksum
        if count > 0:
            sample = collection.get(limit=min(10, count))
            # Create a simple checksum from first few document IDs and their content
            checksum_data = str(sorted(sample["ids"])) + str(count)
            import hashlib
            checksum = hashlib.md5(checksum_data.encode()).hexdigest()
        else:
            checksum = ""
            
        return {
            "exists": True,
            "count": count,
            "checksum": checksum,
        }
    except ValueError:
        return {
            "exists": False,
            "count": 0,
            "checksum": "",
        }


MIN_RELEVANCE = 0.30  # cosine similarity floor for "related" results


def retrieve(
    query: str,
    n_results: int = 5,
    min_score: float = MIN_RELEVANCE,
) -> list[dict]:
    """Return the email thread(s) relevant to the query.

    May return one thread, multiple threads, or an empty list — depending on
    how many candidates exceed `min_score`. Matches the task brief's
    "identify and retrieve the relevant email thread(s)" requirement: the
    system reports exactly the threads it considers relevant, no more.
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

    return [t for t in threads if t["score"] >= min_score]
