"""
TEMPORARY ingestion debugging/QA tool.

Runs the real extraction pipeline (PDF layout extraction -> line
reconstruction -> page classification -> front-matter/people/section
metadata) against one or more PDFs, OUTSIDE of the normal upload/Celery
flow, and writes the resulting structured JSON to disk for inspection with
validate_ingestion.py. It creates one throwaway IngestionJob per PDF to run
the real pipeline steps against (they're written the same way the existing
synthetic-PDF test suite drives the pipeline), then deletes that job, its
logs, and its uploaded file copy immediately afterward -- nothing from this
command is left in the real jobs table.

This is intentionally kept separate from the production upload/publish
path: it does not touch views, serializers, models, or API contracts, and
can be deleted later without affecting the application.

Usage:
    python manage.py extract_debug_json path/to/report.pdf
    python manage.py extract_debug_json path/to/report.pdf --out out.json
    python manage.py extract_debug_json path/to/pdf_dir/ --out-dir path/to/json_dir/

Confidentiality note: this command is meant for PDFs you're allowed to
inspect (synthetic/self-authored test PDFs, or your own real submissions).
It does not print any extracted text to the terminal -- only file paths and
counts -- but the JSON files it writes DO contain full extracted text, so
treat their output directory with the same care as the source PDFs.
"""

import json
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand, CommandError

from ingestion.models import IngestionJob
from ingestion.pipeline.steps.pdf_extraction import PDFExtractionStep
from ingestion.pipeline.steps.line_reconstruction import LineReconstructionStep
from ingestion.pipeline.steps.page_classification import PageClassificationStep
from ingestion.pipeline.steps.metadata_front_matter import MetadataFrontMatterStep
from ingestion.pipeline.steps.metadata_people import MetadataPeopleStep
from ingestion.pipeline.steps.metadata_sections import MetadataSectionsStep

DEBUG_TOOL_USER_EMAIL = "ingestion-debug-tool@local.invalid"

EXTRACTION_STEPS = [
    PDFExtractionStep,
    LineReconstructionStep,
    PageClassificationStep,
    MetadataFrontMatterStep,
    MetadataPeopleStep,
    MetadataSectionsStep,
]


def run_extraction_stages(job):
    context = {"start_time": 0, "stop_pipeline": False}
    for step_cls in EXTRACTION_STEPS:
        context = step_cls().run(job, context)
    return context


def _get_or_create_debug_user():
    User = get_user_model()
    user, _ = User.objects.get_or_create(
        email=DEBUG_TOOL_USER_EMAIL,
        defaults={"first_name": "Ingestion", "last_name": "Debug Tool"},
    )
    return user


def _count_section_nodes(sections):
    total = 0
    for node in sections:
        total += 1
        total += _count_section_nodes(node.get("children") or [])
    return total


def payload_to_debug_json(draft: dict, source_label: str, page_count=None) -> dict:
    """Maps an extracted_payload dict (the shape stored on
    IngestionJob.extracted_payload, whether just produced by a fresh
    pipeline run or read back from an existing job) into the flat debug-JSON
    shape validate_ingestion.py expects. Shared by both extract_debug_json
    (fresh PDF -> pipeline) and export_job_json (existing DB job -> file)
    so the two commands can never quietly drift apart in what they emit."""
    sections = draft.get("project_sections", [])
    return {
        "source_file": source_label,
        "page_count": page_count,
        "metadata": draft.get("project_fields", {}),
        "keywords": draft.get("keywords", []),
        "people_and_roles": draft.get("people_and_roles", []),
        "sections": sections,
        "section_node_count": _count_section_nodes(sections),
        "references": draft.get("references", []),
        "appendices": draft.get("appendices", []),
        "processing_warnings": draft.get("processing_warnings", []),
        "document_metadata": draft.get("document_metadata", {}),
    }


def extract_one(pdf_path: Path, user, label: str | None = None) -> dict:
    """
    `label` is what identifies the document *inside* the emitted JSON. It
    defaults to the filename only for single-file runs the operator started
    by name; batch runs pass a positional label instead, so the JSON on disk
    carries no title-bearing filename either.
    """
    with open(pdf_path, "rb") as fh:
        pdf_bytes = fh.read()

    job = IngestionJob.objects.create(
        file=SimpleUploadedFile(pdf_path.name, pdf_bytes, content_type="application/pdf"),
        original_filename=pdf_path.name,
        uploaded_by=user,
    )
    try:
        context = run_extraction_stages(job)
        draft = context.get("draft_metadata", {})
        return payload_to_debug_json(
            draft,
            label or pdf_path.name,
            page_count=len(context.get("classified_pages", [])),
        )
    finally:
        # Throwaway job: remove it, its logs (cascade), and the uploaded
        # file copy so nothing from this debug run lingers in the real
        # jobs table or on disk.
        try:
            if job.file:
                job.file.delete(save=False)
        except Exception:
            pass
        job.delete()


class Command(BaseCommand):
    help = "Runs the ingestion extraction pipeline against one or more PDFs and writes debug JSON (temporary QA tool, not part of the production upload flow)."

    def add_arguments(self, parser):
        parser.add_argument("path", help="A PDF file, or a directory of PDFs.")
        parser.add_argument("--out", help="Output JSON file path (single-file mode only).")
        parser.add_argument("--out-dir", help="Output directory for JSON files (one per input PDF).")

    def handle(self, *args, **options):
        path = Path(options["path"])
        if not path.exists():
            raise CommandError(f"Path does not exist: {path}")

        user = _get_or_create_debug_user()

        if path.is_dir():
            out_dir = Path(options["out_dir"]) if options.get("out_dir") else path / "_debug_json"
            out_dir.mkdir(parents=True, exist_ok=True)
            pdf_files = sorted(path.glob("*.pdf"))
            if not pdf_files:
                raise CommandError(f"No .pdf files found in {path}")

            # Documents are referred to by position in sorted order, never
            # by filename -- a report's filename normally contains its title.
            # The index matches validate_ingestion.py's "Document #N", which
            # sorts the same directory the same way, so the two line up.
            self.stdout.write(f"Extracting {len(pdf_files)} PDF(s) from {path} -> {out_dir}")
            for index, pdf_path in enumerate(pdf_files, start=1):
                try:
                    result = extract_one(pdf_path, user, label=f"document-{index:03d}")
                except Exception as exc:  # noqa: BLE001 -- one bad PDF shouldn't kill the batch
                    self.stderr.write(
                        self.style.ERROR(f"  FAILED Document #{index}: {type(exc).__name__}")
                    )
                    continue
                out_path = out_dir / f"document_{index:03d}.json"
                out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
                self.stdout.write(
                    f"  OK   Document #{index} -> {out_path.name} "
                    f"({result['section_node_count']} section node(s), "
                    f"{len(result['people_and_roles'])} people)"
                )
            self.stdout.write(self.style.SUCCESS(f"Done. JSON written to {out_dir}"))
            return

        # Single-file mode
        result = extract_one(path, user)
        payload = json.dumps(result, indent=2, ensure_ascii=False)
        if options.get("out"):
            out_path = Path(options["out"])
            out_path.write_text(payload, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote {out_path}"))
        else:
            # See export_job_json: extracted content never goes to stdout.
            raise CommandError(
                "Refusing to write extracted content to stdout. "
                "Pass --out <file>; the JSON stays on disk."
            )
