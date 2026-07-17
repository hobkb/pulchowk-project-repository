"""
Central configuration for the ingestion pipeline.

All paths are resolved relative to this file's location (RAG/src/ingestion/config.py),
NOT the current working directory. This is what makes the pipeline safe to import
from a Django app, a management command, a Celery task, or a plain script --
it always finds the same `docs/`, `registry/`, `logs/`, `extracted/`
folders under the RAG/ project root regardless of where the process was
launched from.

The ingestion pipeline uses PostgreSQL + pgvector for persistent storage.

Content chunks are stored in the `document_chunks` table, while project-level
semantic profiles are stored in the `project_profiles` table. Retrieval is
performed using pgvector HNSW indexes for both content-level semantic search
and project recommendation.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# RAG/  <- this is BASE_DIR
#   src/ingestion/config.py  <- this file
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ----------------------------
# Project Directories
# ----------------------------
DOCS_DIR = BASE_DIR / "docs"
REGISTRY_DIR = BASE_DIR / "registry"
LOG_DIR = BASE_DIR / "logs"
EXTRACTED_DIR = BASE_DIR / "extracted"
PAYLOADS_DIR = EXTRACTED_DIR / "payloads"      # processed_*.json backups
SUMMARY_DIR = EXTRACTED_DIR / "summaries"
METADATA_DIR = EXTRACTED_DIR / "metadata"

# ----------------------------
# Registry File
# ----------------------------
REGISTRY_PATH = REGISTRY_DIR / "ingestion_registry.json"

# ----------------------------
# Logging
# ----------------------------
LOG_FILE = LOG_DIR / "ingestion.log"

# ----------------------------
# Embedding Configuration
# ----------------------------
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384

# ----------------------------
# PostgreSQL Configuration
# ----------------------------
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", 5432))
POSTGRES_DB = os.getenv("POSTGRES_DB", "pulchowk_repository")
POSTGRES_USER = os.getenv("POSTGRES_USER", "postgres")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# ----------------------------
# pgvector Configuration
# ----------------------------
VECTOR_DIMENSION = 384
PROJECT_KEYWORDS_TOP_N = 15
PIPELINE_VERSION = "2.1"

# ----------------------------
# Hashing
# ----------------------------
HASH_ALGORITHM = "sha256"

# ----------------------------
# Timestamp
# ----------------------------
TIME_FORMAT = "%Y-%m-%d %H:%M:%S"

ALL_DIRS = [
    DOCS_DIR,
    REGISTRY_DIR,
    LOG_DIR,
    EXTRACTED_DIR,
    PAYLOADS_DIR,
    SUMMARY_DIR,
    METADATA_DIR,
]


def ensure_directories():
    """Create every directory the pipeline needs, if it doesn't already exist."""
    for directory in ALL_DIRS:
        directory.mkdir(parents=True, exist_ok=True)