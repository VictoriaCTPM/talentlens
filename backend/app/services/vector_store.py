"""
ChromaDB vector store wrapper.
Follows DEC-003: persistent storage on Railway volume / local data/chroma.
"""
import logging
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config.settings import settings

logger = logging.getLogger(__name__)

_COLLECTION_NAME = "talentlens_documents"
_instance: "VectorStore | None" = None


class VectorStore:
    def __init__(self) -> None:
        self._client = chromadb.PersistentClient(
            path=settings.CHROMA_DIR,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(
            "ChromaDB ready at %s — collection '%s' has %d docs",
            settings.CHROMA_DIR,
            _COLLECTION_NAME,
            self._collection.count(),
        )

    # ── Write ────────────────────────────────────────────────────────────────

    def add_chunks(self, chunks: list[dict[str, Any]]) -> None:
        """
        Add document chunks to the collection.

        Each chunk must have:
            id (str)          — unique chunk id, e.g. "doc_42_chunk_0"
            text (str)        — the raw text of the chunk
            embedding (list)  — 384-dim float vector
            metadata (dict)   — flat dict: doc_id, doc_type, project_id,
                                person_name, skills (comma-sep str), date, section
        """
        if not chunks:
            return

        ids = [c["id"] for c in chunks]
        documents = [c["text"] for c in chunks]
        embeddings = [c["embedding"] for c in chunks]
        metadatas = [_sanitize_metadata(c.get("metadata", {})) for c in chunks]

        self._collection.add(
            ids=ids,
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
        )
        logger.debug("Added %d chunks to ChromaDB", len(chunks))

    def delete_by_document(self, document_id: str | int) -> None:
        """Remove all chunks belonging to a document."""
        self._collection.delete(where={"doc_id": str(document_id)})
        logger.debug("Deleted chunks for document_id=%s", document_id)

    # ── Read ─────────────────────────────────────────────────────────────────

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 10,
        where_filter: dict | None = None,
    ) -> list[dict[str, Any]]:
        """
        Cosine similarity search.

        Args:
            query_embedding: 384-dim query vector.
            n_results: max results to return.
            where_filter: ChromaDB metadata filter, e.g. {"doc_type": "resume"}
                          or {"project_id": "5"}.

        Returns:
            List of dicts with keys: id, text, metadata, distance, score.
        """
        count = self._collection.count()
        if count == 0:
            return []

        n_results = min(n_results, count)

        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": n_results,
            "include": ["documents", "metadatas", "distances"],
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = self._collection.query(**kwargs)

        output = []
        for i, chunk_id in enumerate(results["ids"][0]):
            distance = results["distances"][0][i]
            output.append({
                "id": chunk_id,
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": distance,
                "score": round(1 - distance, 4),  # cosine similarity
            })
        return output

    def get_all(self, where_filter: dict | None = None) -> list[dict[str, Any]]:
        """
        Fetch all chunks (optionally filtered by metadata).
        Used to build the BM25 corpus for hybrid search.

        Returns list of dicts: {id, text, metadata}.
        """
        count = self._collection.count()
        if count == 0:
            return []

        kwargs: dict[str, Any] = {"include": ["documents", "metadatas"]}
        if where_filter:
            kwargs["where"] = where_filter

        results = self._collection.get(**kwargs)

        return [
            {
                "id": chunk_id,
                "text": results["documents"][i],
                "metadata": results["metadatas"][i],
            }
            for i, chunk_id in enumerate(results["ids"])
        ]

    def count(self) -> int:
        return self._collection.count()


def get_vector_store() -> VectorStore:
    """Singleton accessor."""
    global _instance
    if _instance is None:
        _instance = VectorStore()
    return _instance


def _sanitize_metadata(meta: dict) -> dict:
    """
    ChromaDB only accepts str, int, float, bool values in metadata.
    Convert lists to comma-separated strings, drop None values.
    """
    clean = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, list):
            clean[k] = ", ".join(str(x) for x in v)
        elif isinstance(v, (str, int, float, bool)):
            clean[k] = v
        else:
            clean[k] = str(v)
    return clean
