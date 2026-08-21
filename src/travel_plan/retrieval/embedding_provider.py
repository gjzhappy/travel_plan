"""Replaceable, local embedding providers for semantic retrieval."""

from abc import ABC, abstractmethod
from collections.abc import Sequence


class EmbeddingProvider(ABC):
    """Provider boundary used by index builders and query repositories."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the vector dimension produced by this provider."""

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    @abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts in input order."""


class BGEEmbeddingProvider(EmbeddingProvider):
    """Local sentence-transformers adapter for BAAI/bge-small-zh-v1.5."""

    MODEL_NAME = "BAAI/bge-small-zh-v1.5"

    def __init__(self, model_path: str | None = None, *, offline: bool = True):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(
            model_path or self.MODEL_NAME,
            device="cpu",
            local_files_only=offline,
        )
        self.model.eval()

    @property
    def dimension(self) -> int:
        return int(self.model.get_sentence_embedding_dimension())

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self.model.encode(
            list(texts),
            batch_size=32,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vectors.astype("float32").tolist()
