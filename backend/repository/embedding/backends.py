"""Embedding backends.

Callers talk to `EmbeddingBackend`, never to SentenceTransformer directly, so
swapping the runtime for an ONNX build or a hosted encoder is a subclass plus
a settings change rather than a rewrite of search, storage, tasks and the API.

Two encode methods because bge models are asymmetric: a passage is encoded
bare, a query behind an instruction prefix. Using the wrong side measurably
degrades retrieval, so the distinction belongs in the interface rather than
in each caller.
"""

from abc import ABC, abstractmethod
from functools import lru_cache

from django.conf import settings


class EmbeddingBackend(ABC):
    """A source of vectors for documents and queries."""

    @property
    @abstractmethod
    def model_version(self):
        """The string stored on every embedding this backend produces."""

    @property
    @abstractmethod
    def dimension(self):
        """Width of the vectors produced, which must match the column."""

    @abstractmethod
    def encode_documents(self, texts):
        """Encode passages. Returns a list of lists of floats."""

    @abstractmethod
    def encode_queries(self, texts):
        """Encode search queries. Returns a list of lists of floats."""


class SentenceTransformerBackend(EmbeddingBackend):
    """sentence-transformers running locally on the CPU.

    The model is loaded on first use rather than at import, so that Django
    management commands, migrations and the test suite do not pay for it
    unless they actually embed something.
    """

    def __init__(self, config=None):
        self._config = config or settings.EMBEDDING
        self._model = None

    # -- interface ---------------------------------------------------
    @property
    def model_version(self):
        return self._config["MODEL_VERSION"]

    @property
    def dimension(self):
        return self._config["DIMENSION"]

    def encode_documents(self, texts):
        return self._encode(list(texts))

    def encode_queries(self, texts):
        prefix = self._config.get("QUERY_PREFIX") or ""
        return self._encode([prefix + t for t in texts])

    # -- internals ---------------------------------------------------
    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self._config["MODEL_NAME"])
            max_len = self._config.get("MAX_SEQ_LENGTH")
            if max_len:
                model.max_seq_length = max_len
            self._model = model
        return self._model

    def _encode(self, texts):
        if not texts:
            return []
        model = self._load()
        vectors = model.encode(
            texts,
            batch_size=self._config.get("BATCH_SIZE", 16),
            normalize_embeddings=self._config.get("NORMALIZE", True),
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return [v.tolist() for v in vectors]


@lru_cache(maxsize=1)
def get_backend():
    """The process-wide backend.

    Cached so a Celery worker or a management command loads the model once
    and reuses it across every project it handles.
    """
    return SentenceTransformerBackend()
