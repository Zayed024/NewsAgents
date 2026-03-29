"""ChromaDB vector store for semantic article search in QueryResponder."""

import os
import chromadb
from src.config import OUTPUT_DIR
from src.models import Article

# Persistent ChromaDB path
CHROMA_DIR = os.path.join(OUTPUT_DIR, "chroma_db")

_client = None
_collection = None


def _get_collection():
    """Get or create the ChromaDB collection."""
    global _client, _collection
    if _collection is None:
        os.makedirs(CHROMA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=CHROMA_DIR)
        _collection = _client.get_or_create_collection(
            name="articles",
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def index_articles(articles: list[Article]):
    """Index articles into ChromaDB for semantic search.

    Args:
        articles: List of articles to index
    """
    collection = _get_collection()

    # Check what's already indexed
    existing = set()
    try:
        result = collection.get()
        existing = set(result["ids"])
    except Exception:
        pass

    new_ids = []
    new_docs = []
    new_metas = []

    for a in articles:
        if a.id in existing:
            continue
        new_ids.append(a.id)
        new_docs.append(f"{a.title}\n\n{a.content}")
        new_metas.append({
            "title": a.title,
            "category": a.category,
            "author": a.author,
            "tags": ",".join(a.tags),
        })

    if new_ids:
        collection.add(
            ids=new_ids,
            documents=new_docs,
            metadatas=new_metas,
        )

    return len(new_ids)


def search_articles(query: str, n_results: int = 5) -> list[dict]:
    """Search articles by semantic similarity to a query.

    Args:
        query: Search query text
        n_results: Number of results to return

    Returns:
        List of dicts with id, title, content snippet, distance
    """
    collection = _get_collection()

    try:
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
        )
    except Exception:
        return []

    output = []
    if results and results["ids"] and results["ids"][0]:
        for i, aid in enumerate(results["ids"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            doc = results["documents"][0][i] if results["documents"] else ""
            dist = results["distances"][0][i] if results["distances"] else 0.0
            output.append({
                "id": aid,
                "title": meta.get("title", ""),
                "content_snippet": doc[:300],
                "distance": dist,
                "category": meta.get("category", ""),
            })

    return output


def clear_index():
    """Clear the article index."""
    global _collection
    try:
        client = chromadb.PersistentClient(path=CHROMA_DIR)
        client.delete_collection("articles")
        _collection = None
    except Exception:
        pass
