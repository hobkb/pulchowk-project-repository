"""
TEMPORARY ingestion QA tool.

Exports the extracted_payload ALREADY STORED on a real IngestionJob --
i.e. exactly what the real website upload flow produced (or, if an admin
has since edited and saved it through the ingestion workflow UI, whatever
is currently there) -- to a JSON file in the same shape
extract_debug_json.py produces, so it can be inspected with
validate_ingestion.py.

Unlike extract_debug_json.py, this does NOT re-run the pipeline and does
NOT create or delete anything -- it only reads a job's current
extracted_payload column. Nothing about the job is modified.

Usage:
    python manage.py export_job_json <job_id> --out job_123.json
    python manage.py export_job_json <job_id> <job_id> <job_id> --out-dir job_json/

Then, from the same terminal:
    python ingestion/tools/validate_ingestion.py job_123.json

Confidentiality: this reads a real submission's full extracted text into a
local JSON file. It only ever operates on the job id(s) you explicitly
pass -- it never scans or lists other jobs -- but treat the output file
with the same care as the source PDF once it's written.
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from ingestion.management.commands.extract_debug_json import payload_to_debug_json
from ingestion.models import IngestionJob


class Command(BaseCommand):
    help = "Exports an existing IngestionJob's stored extracted_payload to debug JSON for validate_ingestion.py (read-only, no re-extraction)."

    def add_arguments(self, parser):
        parser.add_argument("job_id", nargs="+", type=int, help="One or more IngestionJob id(s).")
        parser.add_argument("--out", help="Output JSON file path (single job-id mode only).")
        parser.add_argument("--out-dir", help="Output directory for JSON files (one per job id).")

    def handle(self, *args, **options):
        job_ids = options["job_id"]
        out_dir = Path(options["out_dir"]) if options.get("out_dir") else None
        if out_dir:
            out_dir.mkdir(parents=True, exist_ok=True)

        if len(job_ids) > 1 and not out_dir:
            raise CommandError("Multiple job ids given -- pass --out-dir to write one file per job.")

        for job_id in job_ids:
            try:
                job = IngestionJob.objects.get(id=job_id)
            except IngestionJob.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"No IngestionJob with id={job_id}"))
                continue

            draft = job.extracted_payload or {}
            if not draft:
                self.stderr.write(self.style.WARNING(
                    f"Job {job_id} has no extracted_payload yet (status={job.status}) -- "
                    "nothing to export until the pipeline finishes."
                ))
                continue

            # The source filename usually echoes the project's own title, so
            # the job id alone identifies the document inside the JSON.
            result = payload_to_debug_json(draft, f"job-{job_id}")
            payload = json.dumps(result, indent=2, ensure_ascii=False)

            if out_dir:
                out_path = out_dir / f"job_{job_id}.json"
                out_path.write_text(payload, encoding="utf-8")
                self.stdout.write(self.style.SUCCESS(
                    f"job {job_id} (status={job.status}) -> {out_path} "
                    f"({result['section_node_count']} section node(s), {len(result['people_and_roles'])} people)"
                ))
            elif options.get("out"):
                out_path = Path(options["out"])
                out_path.write_text(payload, encoding="utf-8")
                self.stdout.write(self.style.SUCCESS(f"job {job_id} (status={job.status}) -> {out_path}"))
            else:
                # No stdout fallback: `payload` is the extracted document
                # content (abstract, section bodies, names). Writing it to a
                # terminal would put confidential project text into any log
                # or assistant context reading that terminal, so the command
                # refuses instead of offering the choice.
                raise CommandError(
                    "Refusing to write extracted content to stdout. "
                    "Pass --out <file> or --out-dir <dir>; the JSON stays on disk."
                )
