"""
Local embeddings using fastembed (ONNX backend — no PyTorch required).
Model: all-MiniLM-L6-v2, 384-dim vectors, fully compatible with existing ChromaDB data.
"""
import logging

logger = logging.getLogger(__name__)

_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
_instance: "EmbeddingService | None" = None


class EmbeddingService:
    def __init__(self) -> None:
        logger.info("Loading embedding model %s…", _MODEL_NAME)
        from fastembed import TextEmbedding
        self._model = TextEmbedding(model_name=_MODEL_NAME)
        logger.info("Embedding model loaded.")

    def embed_text(self, text: str) -> list[float]:
        """Embed a single string → 384-dim vector."""
        vectors = list(self._model.embed([text]))
        return vectors[0].tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of strings → list of 384-dim vectors."""
        vectors = list(self._model.embed(texts))
        return [v.tolist() for v in vectors]


def get_embedding_service() -> EmbeddingService:
    """Singleton accessor — model is loaded only once."""
    global _instance
    if _instance is None:
        _instance = EmbeddingService()
    return _instance
