"""
Local Vector Storage Core.

Wraps a persistent Chroma collection. Indexing a filename deletes any chunks
already stored under that filename first, so re-indexing a modified document
cleanly replaces its old chunks rather than duplicating them.

NOTE ON CONSOLIDATION: the original prototype had this class carry its own
private filename->hash JSON registry (`_load_registry` / `save_registry` /
`calculate_file_hash` / `verify_pipeline_delta`) duplicating what
`IngestionRegistry` already did. That's been removed here -- hash tracking
and NEW/DUPLICATE/MODIFIED decisions now live in one place
(`registry.IngestionRegistry`), and this class is only responsible for talking
to Chroma.
"""

import chromadb
from chromadb.utils import embedding_functions

from .config import VECTOR_DB_DIR, COLLECTION_NAME
from .logger import get_logger

logger = get_logger()


class StatefulVectorPipeline:

    def __init__(self, db_path=None, collection_name: str = COLLECTION_NAME):
        self.db_path = str(db_path) if db_path else str(VECTOR_DB_DIR)

        self.chroma_client = chromadb.PersistentClient(path=self.db_path)
        self.embedding_function = embedding_functions.DefaultEmbeddingFunction()
        self.collection = self.chroma_client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
        )
        logger.info(f"Connected to Vector Store at: {self.db_path}")

    def delete_by_filename(self, filename):
        """Remove any chunks already indexed under this filename."""
        try:
            self.collection.delete(where={"source_file": filename})
        except Exception:
            pass  # Collection might be empty, or nothing to delete yet

    def index_payloads_to_vector_store(self, filename, drf_payloads):
        """
        Streams new or modified text chunks into local Chroma storage.
        Purges historical chunks of the same file first, so updates replace
        rather than duplicate.
        """
        if not drf_payloads:
            return

        self.delete_by_filename(filename)

        ids, documents, metadatas = [], [], []
        for record in drf_payloads:
            chunk_id = f"{filename}_chunk_{record['chunk_index']}"
            ids.append(chunk_id)
            documents.append(record["content_body"])

            metadatas.append({
                "source_file": filename,
                "page_number": record["page_number"],
                "page_type": record["page_type"],
                "project_title": record["hierarchy"]["project_title"],
                "chapter": record["hierarchy"]["chapter"],
                "chapter_title": record["hierarchy"]["chapter_title"],
                "section_number": record["hierarchy"]["section_number"],
                "section_title": record["hierarchy"]["section_title"],
            })

        logger.info(f"Streaming {len(documents)} chunks to vector storage for {filename}")
        self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
        logger.info(f"Indexed and committed: {filename}")
