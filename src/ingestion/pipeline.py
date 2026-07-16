"""
Full ingestion pipeline orchestration.

For each PDF in docs/:
  1. Hash it and check the registry: NEW / DUPLICATE (skip) / MODIFIED (re-index).
  2. Extract layout -> reconstruct lines -> classify pages -> semantic chunk.
  3. Transform chunks into DRF-ready payload records.
  4. Back the payload up to extracted/payloads/ as JSON.
  5. Index (or re-index) the payload into the Chroma vector store.
  6. Update the registry.
"""

import json
from datetime import datetime
from pathlib import Path

from .config import DOCS_DIR, PAYLOADS_DIR, REGISTRY_PATH, TIME_FORMAT, ensure_directories
from .hashing import generate_sha256
from .logger import get_logger
from .registry import IngestionRegistry
from .pdf_extraction import PDFLayoutExtractor
from .line_reconstruction import LineReconstructor
from .page_classification import DocumentPageClassifier
from .semantic_chunking import AcademicSemanticChunker
from .payload_transform import DjangoIngestionTransformer
from .vector_store import StatefulVectorPipeline

logger = get_logger()


def process_single_pdf(pdf_path: Path, registry: IngestionRegistry, vector_pipeline: StatefulVectorPipeline) -> str:
    """
    Runs one PDF through the full extraction -> chunk -> transform -> index chain.
    Returns one of: "skipped", "indexed", "modified".
    """
    filename = pdf_path.name
    file_hash = generate_sha256(pdf_path)

    existing_sha256, _existing_record = registry.find_by_filename(filename)
    is_known = existing_sha256 is not None
    is_unchanged = is_known and existing_sha256 == file_hash
    is_modified = is_known and not is_unchanged

    if is_unchanged:
        print(f"Skipping {filename} (already indexed, unchanged).")
        return "skipped"

    if is_modified:
        print(f"Change detected in {filename}, re-processing...")
    else:
        print(f"Processing new file: {filename}")

    # Extraction -> reconstruction -> classification -> chunking -> payload transform
    raw_pages = PDFLayoutExtractor.extract_pages(str(pdf_path))
    reconstructed = LineReconstructor.reconstruct(raw_pages)
    classified = DocumentPageClassifier.classify(reconstructed)
    chunks = AcademicSemanticChunker.chunk_document(classified)
    payloads = DjangoIngestionTransformer.transform_to_payload(chunks)

    # JSON backup
    ensure_directories()
    json_path = PAYLOADS_DIR / f"processed_{pdf_path.stem}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payloads, f, indent=4, ensure_ascii=False)
    logger.info(f"Backup JSON saved to: {json_path}")

    # Vector store indexing (delete-then-insert handles the modified case too)
    vector_pipeline.index_payloads_to_vector_store(filename, payloads)

    # Registry update: drop the stale hash entry (if any) and register the current one
    registry.replace_document(existing_sha256, {
        "sha256": file_hash,
        "filename": filename,
        "chunk_count": len(payloads),
        "timestamp": datetime.now().strftime(TIME_FORMAT),
    })

    print(f"Successfully completed: {filename} ({len(payloads)} chunks)")
    return "modified" if is_modified else "indexed"


def run_full_pipeline(pdf_folder=None) -> dict:
    """
    Processes every PDF found in `pdf_folder` (defaults to config.DOCS_DIR).
    Safe to call repeatedly / on a schedule -- unchanged files are skipped,
    modified files are re-indexed, new files are indexed.
    """
    ensure_directories()
    pdf_folder_path = Path(pdf_folder) if pdf_folder else DOCS_DIR

    registry = IngestionRegistry(REGISTRY_PATH)
    vector_pipeline = StatefulVectorPipeline()

    results = {"indexed": 0, "modified": 0, "skipped": 0, "failed": 0}

    pdf_files = list(pdf_folder_path.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {pdf_folder_path}.")
        return results

    for pdf_path in pdf_files:
        try:
            outcome = process_single_pdf(pdf_path, registry, vector_pipeline)
            results[outcome] += 1
        except Exception as e:
            logger.error(f"Failed processing {pdf_path.name}: {e}")
            print(f"Error processing {pdf_path.name}: {e}")
            results["failed"] += 1

    print("--- CHROMA VEC-STORE INGESTION COMPLETE ---")
    print(f"Operational Storage Path     : {vector_pipeline.db_path}")
    print(f"New                          : {results['indexed']}")
    print(f"Modified & re-indexed        : {results['modified']}")
    print(f"Skipped (unchanged)          : {results['skipped']}")
    print(f"Failed                       : {results['failed']}")
    print(f"Total Database Payload Count : {vector_pipeline.collection.count()} chunks")

    return results
