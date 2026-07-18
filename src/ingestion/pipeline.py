"""
Full PostgreSQL + pgvector ingestion pipeline.

Pipeline:

PDF
 |
Layout Extraction
 |
Line Reconstruction
 |
Page Classification
 |
Metadata Extraction
 |
Semantic Chunking
 |
 +----------------------------+
 |                            |
Content Level             Project Level
(document_chunks)         (project_profiles)

PostgreSQLVectorStore      ProjectVectorStore


Used for:

Content level:
- semantic retrieval
- RAG context retrieval
- document Q&A


Project level:
- similar project recommendation
- project discovery
- project comparison
"""


import json

from datetime import datetime
from pathlib import Path


from .config import (
    DOCS_DIR,
    PAYLOADS_DIR,
    METADATA_DIR,
    REGISTRY_PATH,
    TIME_FORMAT,
    ensure_directories
)


from .hashing import generate_sha256

from .logger import get_logger

from .registry import IngestionRegistry


from .pdf_extraction import PDFLayoutExtractor

from .line_reconstruction import LineReconstructor

from .page_classification import DocumentPageClassifier

from .metadata_extraction import DocumentMetadataExtractor


from .semantic_chunking import AcademicSemanticChunker


from .project_chunking import ProjectLevelChunker


from .payload_transform import DjangoIngestionTransformer


from .document_store import DocumentStore

from .postgres_vector_store import PostgreSQLVectorStore

from .project_vector_store import ProjectVectorStore



logger = get_logger()



def process_single_pdf(
    pdf_path: Path,
    registry: IngestionRegistry,
    document_store: DocumentStore,
    content_store: PostgreSQLVectorStore,
    project_store: ProjectVectorStore
):


    filename = pdf_path.name


    file_hash = generate_sha256(
        pdf_path
    )


    existing_sha256, _ = registry.find_by_filename(
        filename
    )


    if existing_sha256 == file_hash:

        print(
            f"Skipping {filename} (unchanged)"
        )

        return "skipped"



    if existing_sha256:

        print(
            f"Modified file detected: {filename}"
        )

    else:

        print(
            f"New file detected: {filename}"
        )



    # =====================================================
    # 1. PDF Processing
    # =====================================================


    raw_pages = PDFLayoutExtractor.extract_pages(
        str(pdf_path)
    )


    reconstructed = LineReconstructor.reconstruct(
        raw_pages
    )


    classified = DocumentPageClassifier.classify(
        reconstructed
    )



    # =====================================================
    # 2. Document Metadata Extraction
    # =====================================================


    extracted_metadata = (
        DocumentMetadataExtractor.extract(
            classified
        )
    )



    ensure_directories()



    metadata_path = (

        METADATA_DIR /

        f"{pdf_path.stem}.json"

    )



    with open(
        metadata_path,
        "w",
        encoding="utf-8"
    ) as file:


        json.dump(

            extracted_metadata,

            file,

            indent=4,

            ensure_ascii=False

        )



    logger.info(
        f"Metadata extraction saved: {metadata_path}"
    )



    # =====================================================
    # 3. Semantic Content Chunking
    # =====================================================


    chunks = AcademicSemanticChunker.chunk_document(
        classified
    )



    # =====================================================
    # 4. Project Profile Generation
    # =====================================================


    project_title = (
        DjangoIngestionTransformer
        .get_project_title(chunks)
    )


    project_profile = (
        ProjectLevelChunker
        .build_project_profile(
            project_title,
            chunks
        )
    )



    # =====================================================
    # 5. Register Document
    # =====================================================


    document_id = document_store.upsert_document(

        filename=filename,

        project_title=project_title,

        file_hash=file_hash,

        page_count=len(classified)

    )



    # =====================================================
    # 6. Content Payload Creation
    # =====================================================


    payloads = (
        DjangoIngestionTransformer
        .transform_to_payload(
            chunks
        )
    )



    ensure_directories()



    json_path = (

        PAYLOADS_DIR /

        f"processed_{pdf_path.stem}.json"

    )



    with open(
        json_path,
        "w",
        encoding="utf-8"
    ) as file:


        json.dump(

            payloads,

            file,

            indent=4,

            ensure_ascii=False

        )



    logger.info(
        f"Payload backup saved: {json_path}"
    )



    # =====================================================
    # 7. Store Content Chunks
    # =====================================================


    content_store.index_document(

        document_id=document_id,

        payloads=payloads

    )



    # =====================================================
    # 8. Store Project Profile
    # =====================================================


    project_store.upsert_project_profile(

        document_id=document_id,

        profile=project_profile

    )



    # =====================================================
    # 9. Registry Update
    # =====================================================


    registry.replace_document(

        existing_sha256,

        {

            "sha256": file_hash,

            "filename": filename,

            "document_id": document_id,

            "chunk_count": len(payloads),

            "timestamp":
                datetime.now()
                .strftime(
                    TIME_FORMAT
                )

        }

    )



    print(
        f"Completed {filename}: "
        f"{len(payloads)} chunks + 1 project profile + metadata"
    )



    return (

        "modified"

        if existing_sha256

        else

        "indexed"

    )





def run_full_pipeline(
    pdf_folder=None
):


    ensure_directories()



    folder = (

        Path(pdf_folder)

        if pdf_folder

        else DOCS_DIR

    )



    registry = IngestionRegistry(
        REGISTRY_PATH
    )



    document_store = DocumentStore()



    content_store = PostgreSQLVectorStore()


    project_store = ProjectVectorStore()



    results = {

        "indexed":0,

        "modified":0,

        "skipped":0,

        "failed":0

    }



    pdf_files = list(

        folder.glob("*.pdf")

    )



    if not pdf_files:


        print(
            f"No PDFs found in {folder}"
        )


        return results



    for pdf_path in pdf_files:


        try:


            status = process_single_pdf(

                pdf_path,

                registry,

                document_store,

                content_store,

                project_store

            )


            results[status] += 1



        except Exception as error:

            import traceback

            print(
                f"\nFAILED: {pdf_path.name}"
            )

            traceback.print_exc()



            try:

                content_store.connection.rollback()

            except Exception:
                pass



            try:

                project_store.connection.rollback()

            except Exception:
                pass



            try:

                document_store.connection.rollback()

            except Exception:
                pass



            results["failed"] += 1




    print(
        "\n========== INGESTION COMPLETE =========="
    )



    print(
        content_store.describe()
    )


    print(
        project_store.describe()
    )


    print(
        f"Documents: {document_store.count()}"
    )


    print(
        f"Content chunks: {content_store.count()}"
    )


    print(
        f"Project profiles: {project_store.count()}"
    )


    print(
        f"New: {results['indexed']}"
    )


    print(
        f"Modified: {results['modified']}"
    )


    print(
        f"Skipped: {results['skipped']}"
    )


    print(
        f"Failed: {results['failed']}"
    )



    return results