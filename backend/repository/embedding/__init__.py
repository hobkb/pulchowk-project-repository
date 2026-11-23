"""Project-level semantic embeddings.

Public surface for the rest of the backend. Import from here rather than from
the submodules, so the runtime behind it can be replaced without touching
call sites.
"""

from .backends import EmbeddingBackend, get_backend
from .service import (
    GenerationStats,
    active_model_version,
    audit,
    embed_concept,
    embed_query,
    generate_for,
    plan_for,
)
from .text import build_concept_text, build_text, fingerprint

__all__ = [
    "EmbeddingBackend",
    "GenerationStats",
    "active_model_version",
    "audit",
    "build_concept_text",
    "build_text",
    "embed_concept",
    "embed_query",
    "fingerprint",
    "generate_for",
    "get_backend",
    "plan_for",
]
