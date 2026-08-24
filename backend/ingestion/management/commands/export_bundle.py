"""
Write this database's published projects out as a portable bundle.

Run this on each machine after ingesting; hand the resulting folder to
whoever holds the master database, and they run `import_bundle` on each in
turn. See `_bundle.py` for why the transfer uses natural keys rather than
a SQL dump.

Output is counts and positional indices only. Project titles, filenames and
section text are confidential and stay inside the bundle files, which never
reach a terminal.
"""

import json
import shutil
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError

from ingestion.models import IngestionJob
from repository.models import Project

from ._bundle import (
    BUNDLE_VERSION,
    MANIFEST_NAME,
    PDF_DIR,
    PROJECT_DIR,
    project_identity,
)


class Command(BaseCommand):
    help = "Export published projects as a portable bundle for merging."

    def add_arguments(self, parser):
        parser.add_argument(
            "--out",
            required=True,
            help="Directory to write the bundle into. Created if absent.",
        )
        parser.add_argument(
            "--source",
            default="",
            help="Short label for who produced this bundle, e.g. 'asha'.",
        )
        parser.add_argument(
            "--skip-pdfs",
            action="store_true",
            help="Do not copy source PDFs. Smaller, but the master database "
                 "will have no document to re-extract from later.",
        )

    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        out = Path(options["out"])
        projects_dir = out / PROJECT_DIR
        pdfs_dir = out / PDF_DIR
        projects_dir.mkdir(parents=True, exist_ok=True)
        if not options["skip_pdfs"]:
            pdfs_dir.mkdir(parents=True, exist_ok=True)

        projects = (
            Project.objects.filter(status="Published")
            .select_related("department", "research_group")
            .prefetch_related(
                "project_people__person",
                "project_keywords__keyword",
                "project_domains__domain",
                "sections",
                "references",
            )
            .order_by("id")
        )

        exported = 0
        pdfs_copied = 0
        pdfs_missing = 0
        people_written = 0
        sections_written = 0

        for index, project in enumerate(projects, start=1):
            job = (
                IngestionJob.objects.filter(published_project=project)
                .order_by("-created_at")
                .first()
            )
            record = self._serialize(project, job)

            (projects_dir / f"project_{index:04d}.json").write_text(
                json.dumps(record, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            exported += 1
            people_written += len(record["people"])
            sections_written += len(record["sections"])

            if not options["skip_pdfs"] and job is not None and job.file:
                try:
                    source = Path(job.file.path)
                    if source.exists():
                        shutil.copy2(source, pdfs_dir / f"project_{index:04d}.pdf")
                        record["pdf"] = f"project_{index:04d}.pdf"
                        (projects_dir / f"project_{index:04d}.json").write_text(
                            json.dumps(record, indent=2, ensure_ascii=False, default=str),
                            encoding="utf-8",
                        )
                        pdfs_copied += 1
                    else:
                        pdfs_missing += 1
                except (ValueError, OSError):
                    # A storage backend without a local path, or an
                    # unreadable file. Reported as a count; the exception
                    # text would name the file.
                    pdfs_missing += 1
            elif not options["skip_pdfs"]:
                pdfs_missing += 1

        manifest = {
            "bundle_version": BUNDLE_VERSION,
            "source": options["source"],
            "project_count": exported,
        }
        (out / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )

        self.stdout.write(self.style.SUCCESS(f"Bundle written to {out}"))
        self.stdout.write(f"  projects exported...: {exported}")
        self.stdout.write(f"  people records......: {people_written}")
        self.stdout.write(f"  section rows........: {sections_written}")
        self.stdout.write(f"  PDFs copied.........: {pdfs_copied}")
        if pdfs_missing:
            self.stdout.write(
                self.style.WARNING(
                    f"  PDFs unavailable....: {pdfs_missing} "
                    "(those projects cannot be re-extracted after merging)"
                )
            )
        if not exported:
            raise CommandError("No published projects to export.")

    # ------------------------------------------------------------------

    def _serialize(self, project, job):
        return {
            "identity": project_identity(
                title=project.title,
                batch=project.batch,
                file_hash=getattr(job, "file_hash", None),
            ),
            "fields": {
                "title": project.title,
                "abstract": project.abstract,
                "description": project.description,
                "project_type": project.project_type,
                "academic_level": project.academic_level,
                "batch": project.batch,
                "cluster": project.cluster,
                "language": project.language,
                "github_url": project.github_url,
                "doi_url": project.doi_url,
                "publication_url": project.publication_url,
                "demo_url": project.demo_url,
                "submitted_at": project.submitted_at,
                "approved_at": project.approved_at,
                # Organisations travel by name: every database seeds the
                # same six departments from the same migration, so the name
                # resolves locally without carrying an id across.
                "department_name": (
                    project.department.name if project.department_id else ""
                ),
                "research_group_name": (
                    project.research_group.name if project.research_group_id else ""
                ),
            },
            "people": [self._person(pp) for pp in project.project_people.all()],
            "sections": [
                {
                    "heading": s.heading,
                    "canonical_section": s.canonical_section,
                    "heading_level": s.heading_level,
                    "display_order": s.display_order,
                    "content": s.content,
                    "page_start": s.page_start,
                    "page_end": s.page_end,
                    "word_count": s.word_count,
                }
                for s in project.sections.all().order_by("display_order")
            ],
            "keywords": [pk.keyword.name for pk in project.project_keywords.all()],
            "domains": [pd.domain.name for pd in project.project_domains.all()],
            "references": [
                {"title": r.title, "citation": r.citation, "url": r.url}
                for r in project.references.all()
            ],
            "job": self._job(job),
        }

    def _person(self, project_person):
        person = project_person.person
        record = {
            "full_name": person.full_name,
            "email": person.email or "",
            "role": project_person.role,
            "display_order": project_person.display_order,
            "kind": "person",
        }

        # Person -> Student/Faculty is multi-table inheritance, so a missing
        # subtype raises DoesNotExist rather than returning None.
        try:
            student = person.student
        except ObjectDoesNotExist:
            student = None
        if student is not None:
            record.update(
                kind="student",
                roll_number=student.roll_number,
                academic_level=student.academic_level,
            )
            return record

        try:
            faculty = person.faculty
        except ObjectDoesNotExist:
            faculty = None
        if faculty is not None:
            record.update(
                kind="faculty",
                title=faculty.title or "",
                designation=faculty.designation or "",
            )
        return record

    def _job(self, job):
        if job is None:
            return None
        return {
            "original_filename": job.original_filename,
            "file_hash": job.file_hash,
            "status": job.status,
            "extracted_payload": job.extracted_payload,
        }
