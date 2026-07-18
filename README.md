# RAG Ingestion Pipeline

Automated, hash-based, incremental PDF ingestion pipeline for the Pulchowk
Project Repository. Built as modular Python components for seamless integration
with Django and powered by PostgreSQL + pgvector for semantic document retrieval.

## Folder structure

```text
RAG/
├── database/
│   └── schema.sql                 # PostgreSQL + pgvector schema
├── docs/                          # Drop PDFs here
├── extracted/
│   ├── metadata/
│   ├── payloads/                  # Processed payload backups
│   └── summaries/
├── logs/
│   └── ingestion.log
├── registry/
│   └── ingestion_registry.json    # NEW / MODIFIED / DUPLICATE tracking
├── src/
│   └── ingestion/
│       ├── config.py
│       ├── hashing.py
│       ├── heading_utils.py
│       ├── line_reconstruction.py
│       ├── logger.py
│       ├── page_classification.py
│       ├── payload_transform.py
│       ├── pdf_extraction.py
│       ├── pipeline.py
│       ├── postgres_vector_store.py
│       ├── project_level_chunking.py
│       ├── project_vector_store.py
│       ├── registry.py
│       └── semantic_chunking.py
├── check_sections.py
├── eval.py
├── query_similar_projects.py
├── requirements.txt
├── reset_db.py
├── run_content.py
├── run_evaluation.py
├── run_ingestion.py
├── verify_chroma.py
└── verify_ingestion.py
```
## Running it

```bash
cd RAG
pip install -r requirements.txt
python run_ingestion.py            # processes everything in docs/
python run_ingestion.py /other/pdf/folder
```

For Django, don't shell out to the script — import the function directly,
e.g. in a management command or a Celery task:

```python
from src.ingestion.pipeline import run_full_pipeline
run_full_pipeline()
```

Because `config.py` resolves `BASE_DIR` from its own file location (not
`Path.cwd()`), this works identically no matter what process or working
directory calls it.

## Migrating your existing data

Your current `RAG/docs`, `RAG/chroma_db`, `RAG/registry`, `RAG/logs` folders
can be copied straight into this structure as-is:

- `docs/*.pdf` → `RAG/docs/`
- `chroma_db/` → `RAG/chroma_db/` (as long as it used the same collection
  name / embedding function, it'll be picked up automatically)
- Old `registry/ingestion_registry.json`, if you have one from Prototype V2,
  is compatible with the new `IngestionRegistry` schema and can be dropped
  in as-is.
- Any loose `processed_*.json` files sitting in the RAG root should move
  into `extracted/payloads/` to keep the root clean — the pipeline now
  writes them there automatically.

## What changed from the notebook, and why

The uploaded `.ipynb`-turned-`.py` had been edited by re-running and
re-pasting cells, which left it in a state where, if you ran it top to
bottom, it would **not have completed successfully**. Two things were fixed;
everything else is the same document-processing logic, just organized:

1. **Two crashing bugs fixed.**
   - `run_full_pipeline` called `get_file_hash(pdf_path)`, which was never
     defined anywhere in the file (only `generate_sha256` and
     `StatefulVectorPipeline.calculate_file_hash` existed). Fixed by using
     the one surviving hashing function (`hashing.generate_sha256`).
   - `StatefulVectorPipeline(persist_directory=PERSIST_DIR)` was called, but
     the final version of that class's `__init__` only accepted `db_path`,
     not `persist_directory` — this would raise a `TypeError`. Fixed by
     using the correct parameter name.

2. **Duplicate class definitions resolved.** `PDFLayoutExtractor`,
   `LineReconstructor`, `DocumentPageClassifier`, `AcademicSemanticChunker`,
   `DjangoIngestionTransformer`, and `StatefulVectorPipeline` were each
   defined twice in the notebook (Python silently used the second one).
   Each now exists exactly once, using the logic from that final/live
   definition, so behavior is unchanged from what actually ran.

3. **Two duplicate-tracking systems merged into one, as requested.**
   The notebook had `IngestionRegistry` (rich, per-document, actually used
   by `run_full_pipeline`) *and* a second, simpler filename→hash map living
   privately inside `StatefulVectorPipeline` (`verify_pipeline_delta`) that
   could detect modified files but was never actually called. Per your
   choice, that modified-file detection is now wired in — but instead of
   keeping two separate hash stores, it's built on `IngestionRegistry`
   alone via `find_by_filename()`. Result: new files are indexed, unchanged
   files are skipped, and modified files are automatically re-indexed
   (old chunks for that filename are deleted from Chroma before the new
   ones are added).

4. **Unused/dead-code classes dropped, per your choice:**
   `PDFValidator`, `Document` (dataclass), `DocumentFactory`,
   `DocumentStatus`, `LocalPipelineExporter`, and the commented-out
   `V2ProjectVectorIngestor` block. None of these were called by
   `run_full_pipeline` in the original file.

5. **Unused imports dropped:** `PyMuPDFLoader`, `RecursiveCharacterTextSplitter`,
   `HuggingFaceEmbeddings`, `langchain_chroma` — leftovers from an earlier
   (V1) version of the pipeline that the current code doesn't call.

6. **`processed_*.json` backups** now write to `extracted/payloads/`
   instead of the current working directory, so they don't scatter into
   wherever the script happens to be launched from.

No chunking, classification, title-extraction, or embedding logic was
changed — every regex, heuristic, and metadata field name is byte-for-byte
what the final version of each class in your notebook produced.

## A note on the embedding model

`StatefulVectorPipeline` uses Chroma's `DefaultEmbeddingFunction`
(`all-MiniLM-L6-v2` via ONNX), same as your original. The first time it
runs, Chroma downloads the ONNX model (~90MB) — make sure the machine
running this has normal internet access on first run, or pre-populate
`~/.cache/chroma/onnx_models/`.
