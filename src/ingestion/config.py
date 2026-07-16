"""
Central configuration for the ingestion pipeline.

All paths are resolved relative to this file's location (RAG/src/ingestion/config.py),
NOT the current working directory. This is what makes the pipeline safe to import
from a Django app, a management command, a Celery task, or a plain script --
it always finds the same `docs/`, `chroma_db/`, `registry/`, `logs/` folders
under the RAG/ project root regardless of where the process was launched from.
"""

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
VECTOR_DB_DIR = BASE_DIR / "chroma_db"
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
# Embedding / Vector Store Configuration
# ----------------------------
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384
COLLECTION_NAME = "ioe_thesis_knowledge_base"

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
    VECTOR_DB_DIR,
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
