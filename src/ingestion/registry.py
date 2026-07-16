"""
Ingestion Registry Manager.

Uses SHA-256 as the primary document identifier, keyed in a JSON file at
registry/ingestion_registry.json.

NOTE ON CONSOLIDATION: the original prototype kept two separate hash
registries -- this one (rich, per-document metadata) and a second, simpler
filename->hash map that lived privately inside StatefulVectorPipeline and was
never actually wired up. Both existed to answer the same question ("have I
seen this file before, and has it changed?"), so they've been merged into
this single registry. `find_by_filename` is what now powers modified-file
detection.
"""

import json

from .logger import get_logger

logger = get_logger()


class IngestionRegistry:
    """Handles all registry operations for the ingestion pipeline."""

    def __init__(self, registry_path):
        self.registry_path = registry_path
        self.registry = self.load()

    def load(self):
        """Load registry from disk, creating an empty one if it doesn't exist."""
        if not self.registry_path.exists():
            registry = {"documents": {}}
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_path, "w") as f:
                json.dump(registry, f, indent=4)
            return registry

        with open(self.registry_path, "r") as f:
            return json.load(f)

    def save(self):
        """Save registry to disk (Path values are serialized as posix strings)."""

        def json_serializer(obj):
            if hasattr(obj, "as_posix"):
                return obj.as_posix()
            return str(obj)

        with open(self.registry_path, "w") as f:
            json.dump(self.registry, f, indent=4, default=json_serializer)

    def document_exists(self, sha256):
        """Check if a document with this exact content hash already exists."""
        return sha256 in self.registry["documents"]

    def get_document(self, sha256):
        """Return document metadata for a given hash."""
        return self.registry["documents"].get(sha256)

    def find_by_filename(self, filename):
        """
        Look up the most recently registered entry for a given filename.

        Returns (sha256, record) if found, otherwise (None, None).
        Used to tell NEW vs DUPLICATE vs MODIFIED apart for a given file.
        """
        for sha256, record in self.registry["documents"].items():
            if record.get("filename") == filename:
                return sha256, record
        return None, None

    def add_document(self, document_data):
        """Register a newly indexed document."""
        sha256 = document_data["sha256"]
        self.registry["documents"][sha256] = document_data
        self.save()
        logger.info(f"Document registered: {sha256}")

    def replace_document(self, old_sha256, document_data):
        """
        Register a document that replaces a previous (now-stale) hash entry.
        Used when a file has been modified since it was last indexed.
        """
        if old_sha256 and old_sha256 in self.registry["documents"]:
            del self.registry["documents"][old_sha256]
        self.add_document(document_data)

    def update_document(self, sha256, updates):
        """Update fields on an existing document entry."""
        if sha256 in self.registry["documents"]:
            self.registry["documents"][sha256].update(updates)
            self.save()
            logger.info(f"Registry updated: {sha256}")

    def remove_document(self, sha256):
        """Remove a document entry entirely."""
        if sha256 in self.registry["documents"]:
            del self.registry["documents"][sha256]
            self.save()
            logger.info(f"Document removed: {sha256}")

    def total_documents(self):
        """Return the count of currently registered documents."""
        return len(self.registry["documents"])
