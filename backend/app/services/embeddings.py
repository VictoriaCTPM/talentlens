"""
Local embeddings using sentence-transformers all-MiniLM-L6-v2.
Follows DEC-002: 100% free, data never leaves server, runs on CPU.
"""
import logging

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_instance: "EmbeddingService | None" = None


class EmbeddingService:
    def __init__(self) -> None:
        logger.info("Loading embedding model %s (first load ~80MB download)…", _MODEL_NAME)
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(_MODEL_NAME)
        logger.info("Embedding model loaded.")

    def embed_text(self, text: str) -> list[float]:
        """Embed a single string → 384-dim vector."""
        vector = self._model.encode(text, convert_to_numpy=True)
        return vector.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of strings → list of 384-dim vectors."""
        vectors = self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]


def get_embedding_service() -> EmbeddingService:
    """Singleton accessor — model is loaded only once."""
    global _instance
    if _instance is None:
        _instance = EmbeddingService()
    return _instance
