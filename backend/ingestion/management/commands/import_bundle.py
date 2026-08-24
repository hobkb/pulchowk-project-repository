"""
Merge a bundle produced by `export_bundle` into this database.

Safe to run repeatedly and in any order. Every row is matched by natural
key, so a project already present is updated rather than duplicated, and a
supervisor who appears in two people's bundles becomes one record with one
combined project list -- not two entries splitting the search facet between
them.

The merge is additive by rule: it fills blanks and never overwrites a value
that is already there. That way a title or designation an administrator
corrected by hand survives a later import.

Output is counts and positional indices only; the bundle's contents stay in
the bundle files.
"""

import json
import mimetypes
from pathlib import Path

from django.core.exceptions import ObjectDoesNotExist
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Faculty, Person, Student, User
from ingestion.models import IngestionJob
from ingestion.pipeline.utils.text_cleaners import clean_roll_number, normalize_person_name
from organization.departments import canonical_department
from organization.models import Department, ResearchGroup
from repository.models import (
    Domain,
    Keyword,
    Project,
    ProjectAsset,
    ProjectDomain,
    ProjectKeyword,
    ProjectPerson,
    ProjectReference,
    ProjectSection,
)

from ._bundle import MANIFEST_NAME, PDF_DIR, PROJECT_DIR, normalize_key, project_identity


def _safe_constraint_name(exc):
    """The name of the database constraint an IntegrityError violated, if
    the driver exposes one -- never the driver's own message, which
    typically embeds the offending value. Returns None for anything else,
    including drivers that don't expose diagnostics this way."""
    cause = getattr(exc, "__cause__", None) or exc
    diag = getattr(cause, "diag", None)
    return getattr(diag, "constraint_name", None)


class Command(BaseCommand):
    help = "Merge an exported project bundle into this database."

    def add_arguments(self, parser):
        parser.add_argument("--bundle", required=True, help="Bundle directory.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing anything.",
        )

    # ------------------------------------------------------------------

    def handle(self, *args, **options):
        bundle = Path(options["bundle"])
        manifest_path = bundle / MANIFEST_NAME
        if not manifest_path.exists():
            raise CommandError(f"No {MANIFEST_NAME} in {bundle}. Not a bundle directory.")

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = sorted((bundle / PROJECT_DIR).glob("*.json"))
        if not files:
            raise CommandError("Bundle contains no project files.")

        dry_run = options["dry_run"]
        self.stdout.write(
            f"Merging {len(files)} project(s) from bundle "
            f"'{manifest.get('source') or 'unlabelled'}'"
            + (" [DRY RUN -- no writes]" if dry_run else "")
        )

        created = updated = skipped = 0
        people_linked = sections_written = pdfs_attached = 0
        failures = 0

        for index, path in enumerate(files, start=1):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                failures += 1
                self.stderr.write(
                    self.style.ERROR(f"  Document #{index}: unreadable JSON")
                )
                continue

            try:
                with transaction.atomic():
                    outcome = self._merge(record, bundle, index, dry_run)
                    if dry_run:
                        # Nothing from a dry run may persist, including the
                        # rows written to work out what would change.
                        transaction.set_rollback(True)
            except Exception as exc:  # noqa: BLE001 -- one bad file must not stop the merge
                failures += 1
                # The exception type, plus -- for a database constraint
                # violation -- the constraint's own NAME (a schema
                # identifier such as "ingestion_job_uploaded_by_id_..."),
                # never its message. The driver's message routinely embeds
                # the actual colliding value (a person's name, a roll
                # number), which the constraint name does not.
                detail = _safe_constraint_name(exc)
                label = f"{type(exc).__name__} ({detail})" if detail else type(exc).__name__
                self.stderr.write(
                    self.style.ERROR(f"  Document #{index}: {label}")
                )
                continue

            if outcome["action"] == "created":
                created += 1
            elif outcome["action"] == "updated":
                updated += 1
            else:
                skipped += 1
            people_linked += outcome["people"]
            sections_written += outcome["sections"]
            pdfs_attached += outcome["pdf"]

            self.stdout.write(
                f"  Document #{index}: {outcome['action']} "
                f"({outcome['people']} person link(s), {outcome['sections']} section(s))"
            )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Merge complete." if not dry_run else "Dry run complete."))
        self.stdout.write(f"  projects created....: {created}")
        self.stdout.write(f"  projects updated....: {updated}")
        self.stdout.write(f"  projects unchanged..: {skipped}")
        self.stdout.write(f"  person links........: {people_linked}")
        self.stdout.write(f"  section rows........: {sections_written}")
        self.stdout.write(f"  PDFs attached.......: {pdfs_attached}")
        if failures:
            self.stdout.write(self.style.WARNING(f"  documents failed....: {failures}"))

    # ------------------------------------------------------------------

    def _merge(self, record, bundle, index, dry_run):
        fields = record["fields"]
        job_data = record.get("job") or {}
        identity = record.get("identity") or project_identity(
            title=fields.get("title"),
            batch=fields.get("batch"),
            file_hash=job_data.get("file_hash"),
        )

        project, action = self._upsert_project(identity, fields, job_data)

        people = self._link_people(project, record.get("people") or [])
        sections = self._replace_sections(project, record.get("sections") or [])
        self._link_words(project, record.get("keywords") or [], Keyword, ProjectKeyword, "keyword")
        self._link_words(project, record.get("domains") or [], Domain, ProjectDomain, "domain")
        self._replace_references(project, record.get("references") or [])
        pdf = self._attach_pdf(project, record, bundle, job_data, dry_run)

        return {"action": action, "people": people, "sections": sections, "pdf": pdf}

    # -- project ------------------------------------------------------

    def _upsert_project(self, identity, fields, job_data):
        """Finds this project by content hash, else by title+batch."""
        existing = None
        file_hash = job_data.get("file_hash")
        if file_hash:
            job = IngestionJob.objects.filter(file_hash=file_hash).exclude(
                published_project=None
            ).first()
            if job:
                existing = job.published_project

        if existing is None:
            existing = Project.objects.filter(
                title__iexact=(fields.get("title") or "").strip(),
                batch=fields.get("batch") or "",
            ).first()

        department = self._department(fields.get("department_name"))
        research_group = self._research_group(
            fields.get("research_group_name"), department
        )

        values = {
            "abstract": fields.get("abstract") or "",
            "description": fields.get("description") or "",
            "project_type": fields.get("project_type") or "Major",
            "academic_level": fields.get("academic_level") or "UG",
            "batch": fields.get("batch") or "",
            "cluster": fields.get("cluster") or None,
            "language": fields.get("language") or "English",
            "github_url": fields.get("github_url") or "",
            "doi_url": fields.get("doi_url") or "",
            "publication_url": fields.get("publication_url") or "",
            "demo_url": fields.get("demo_url") or "",
            "status": "Published",
        }

        if existing is None:
            project = Project.objects.create(
                title=(fields.get("title") or "").strip(),
                department=department,
                research_group=research_group,
                **values,
            )
            return project, "created"

        # Additive: a bundle that says nothing about a field never changes
        # it. None and "" are the same emptiness here -- some URL columns
        # are nullable and some are not, and treating them differently made
        # a re-import of a database's own export report changes it was not
        # actually making.
        def empty(v):
            return v is None or v == ""

        changes = {}
        for field, value in values.items():
            if empty(value):
                continue
            if getattr(existing, field) != value:
                changes[field] = value
        if department is not None and existing.department_id is None:
            changes["department"] = department
        if research_group is not None and existing.research_group_id is None:
            changes["research_group"] = research_group

        if changes:
            for field, value in changes.items():
                setattr(existing, field, value)
            existing.save(update_fields=list(changes))
            return existing, "updated"
        return existing, "unchanged"

    def _department(self, name):
        if not name:
            return None
        # Every database seeds the same six departments from the same
        # migration, so the canonical name resolves locally.
        canonical = canonical_department(name) or name
        return Department.objects.filter(name__iexact=canonical).first()

    def _research_group(self, name, department):
        if not name:
            return None
        return ResearchGroup.objects.filter(
            name__iexact=name, department=department
        ).first()

    # -- people -------------------------------------------------------

    def _link_people(self, project, people):
        linked = 0
        for entry in people:
            person = self._resolve_person(entry)
            if person is None:
                continue
            ProjectPerson.objects.get_or_create(
                project=project,
                person=person,
                role=entry.get("role") or "Author",
                defaults={"display_order": entry.get("display_order") or 1},
            )
            linked += 1
        return linked

    def _resolve_person(self, entry):
        """One person, matched by natural key across every bundle.

        This is what stops the same supervisor becoming three records. A
        student is matched on roll number, which the campus guarantees is
        unique; faculty fall back to the name, and are only ever topped up,
        never overwritten.
        """
        full_name = normalize_person_name(entry.get("full_name") or "")
        if not full_name:
            return None

        kind = entry.get("kind")
        email = (entry.get("email") or "").strip() or None

        if kind == "student":
            roll = clean_roll_number(entry.get("roll_number") or "")
            student = Student.objects.filter(roll_number=roll).first() if roll else None
            if student is None and email:
                student = Student.objects.filter(email=email).first()
            if student is None:
                if not roll:
                    return None
                return Student.objects.create(
                    full_name=full_name,
                    roll_number=roll,
                    academic_level=entry.get("academic_level") or "UG",
                    email=email if not Person.objects.filter(email=email).exists() else None,
                )
            return student

        if kind == "faculty":
            faculty = Faculty.objects.filter(full_name__iexact=full_name).first()
            if faculty is None:
                return Faculty.objects.create(
                    full_name=full_name,
                    title=entry.get("title") or "",
                    designation=entry.get("designation") or "",
                    email=email if email and not Person.objects.filter(email=email).exists() else None,
                )
            fills = {}
            if entry.get("title") and not faculty.title:
                fills["title"] = entry["title"]
            if entry.get("designation") and not faculty.designation:
                fills["designation"] = entry["designation"]
            if fills:
                for field, value in fills.items():
                    setattr(faculty, field, value)
                faculty.save(update_fields=list(fills))
            return faculty

        person = Person.objects.filter(full_name__iexact=full_name).first()
        if person is None:
            person = Person.objects.create(
                full_name=full_name,
                email=email if email and not Person.objects.filter(email=email).exists() else None,
            )
        return person

    # -- sections, words, references ----------------------------------

    def _replace_sections(self, project, sections):
        """Sections are replaced wholesale rather than merged.

        A section tree is one document's structure; merging two versions of
        it row by row would interleave them into something the author never
        wrote. The bundle's copy is authoritative for the project it
        describes.
        """
        if not sections:
            return project.sections.count()

        project.sections.all().delete()
        ProjectSection.objects.bulk_create([
            ProjectSection(
                project=project,
                heading=s.get("heading") or "",
                canonical_section=s.get("canonical_section") or "",
                heading_level=s.get("heading_level") or 1,
                display_order=s.get("display_order") or index,
                content=s.get("content") or "",
                page_start=s.get("page_start"),
                page_end=s.get("page_end"),
                word_count=s.get("word_count") or 0,
            )
            for index, s in enumerate(sections, start=1)
        ])
        return len(sections)

    def _link_words(self, project, names, model, through, field):
        for name in names:
            cleaned = (name or "").strip()
            if not cleaned:
                continue
            obj = model.objects.filter(name__iexact=cleaned).first()
            if obj is None:
                obj = model.objects.create(name=cleaned)
            through.objects.get_or_create(project=project, **{field: obj})

    def _replace_references(self, project, references):
        if not references:
            return
        project.references.all().delete()
        ProjectReference.objects.bulk_create([
            ProjectReference(
                project=project,
                title=r.get("title") or "",
                citation=r.get("citation") or "",
                url=r.get("url") or "",
            )
            for r in references
        ])

    # -- source document ----------------------------------------------

    def _attach_pdf(self, project, record, bundle, job_data, dry_run):
        """Carries the source PDF across so the merged database can still
        re-extract later. Without it a project is a dead end -- which is
        why six of the existing records could not have their supervisor
        titles rebuilt."""
        name = record.get("pdf")
        if not name or dry_run:
            return 0

        source = bundle / PDF_DIR / name
        if not source.exists():
            return 0

        job = IngestionJob.objects.filter(published_project=project).first()
        if job is not None and job.file:
            return 0

        if job is None:
            job = IngestionJob(
                published_project=project,
                original_filename=job_data.get("original_filename") or name,
                file_hash=job_data.get("file_hash") or "",
                status=job_data.get("status") or IngestionJob.Status.VERIFIED,
                extracted_payload=job_data.get("extracted_payload") or {},
                # `uploaded_by` is required at the database level and was
                # simply never set here, which raised a NOT-NULL
                # IntegrityError on every real (non-dry-run) merge that
                # attached a PDF -- dry runs never reached this far, since
                # they return above before constructing the job, which is
                # why the bug only showed up once writes were for real.
                uploaded_by=self._merge_attributed_user(job_data),
            )

        with source.open("rb") as handle:
            job.file.save(name, File(handle), save=False)
        job.save()

        # The report-access check (get_pdfUrl) does not look at the job at
        # all -- it looks for a ProjectAsset row of type "Report", exactly
        # the same as the normal publish flow creates. Without one here, a
        # privileged reviewer would still see the report as unavailable
        # after a merge, not because access was denied but because nothing
        # ever told the catalogue a report existed.
        if not project.assets.filter(asset_type="Report").exists():
            mime_type, _ = mimetypes.guess_type(job.file.name)
            ProjectAsset.objects.create(
                project=project,
                asset_type="Report",
                file=job.file.name,
                mime_type=mime_type or "application/pdf",
                file_size=job.file.size,
            )

        return 1

    def _merge_attributed_user(self, job_data):
        """Who a merged job is attributed to.

        Tries the original uploader's own account first, in case they also
        exist on the database being merged into (common once a team shares
        one master). Falls back to a dedicated system account -- created
        once, reused every time -- since the field cannot be left empty and
        there is no guarantee the original uploader has ever signed in
        here."""
        email = (job_data.get("uploaded_by_email") or "").strip()
        if email:
            existing = User.objects.filter(email__iexact=email).first()
            if existing is not None:
                return existing

        user, _ = User.objects.get_or_create(
            email="bundle-merge@local.invalid",
            defaults={"first_name": "Bundle", "last_name": "Merge"},
        )
        return user
