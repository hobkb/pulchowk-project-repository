"""
Re-runs people extraction (authors + supervisors) against the ORIGINAL PDF
of already-published projects and fills in what the older, weaker extraction
logic missed -- principally supervisors, which were being dropped for most
documents because supervisor detection previously required an exact bare
"Supervisor" label line.

Additive by design. It only ever CREATES ProjectPerson rows that are absent;
it never edits, re-roles, or deletes an existing person, never touches
project fields, sections, keywords, or references, and never changes a
project's status. So a record an admin has already corrected by hand cannot
be overwritten by re-running this.

The extracted payload stored on the job is not re-used, because for these
older jobs it is precisely the artifact of the old logic. The real PDF is
re-run through the same extraction steps the live pipeline uses
(PDFExtractionStep -> ... -> MetadataPeopleStep) so results match exactly
what a fresh upload would produce today.

Usage:
    python manage.py reprocess_people --dry-run          # report only, no writes
    python manage.py reprocess_people                    # fill in missing supervisors
    python manage.py reprocess_people --include-authors  # also add missing authors
    python manage.py reprocess_people --project-id 12    # one project
    python manage.py reprocess_people --all-projects     # include ones that already
                                                         # have a supervisor

Confidentiality note: this reads real uploaded project PDFs. It prints only
counts and extracted person NAMES (which are published metadata anyway) --
never document body text.
"""

from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from ingestion.models import IngestionJob
from ingestion.pipeline.steps.line_reconstruction import LineReconstructionStep
from ingestion.pipeline.steps.metadata_front_matter import MetadataFrontMatterStep
from ingestion.pipeline.steps.metadata_people import MetadataPeopleStep
from ingestion.pipeline.steps.page_classification import PageClassificationStep
from ingestion.pipeline.steps.pdf_extraction import PDFExtractionStep
from ingestion.pipeline.utils.text_cleaners import clean_roll_number
from ingestion.views import JobPublishAPIView
from accounts.models import Faculty
from repository.models import Project, ProjectPerson

SUPERVISORY_ROLES = {"Supervisor", "Co-Supervisor"}

# Only the steps needed to reach people extraction -- section extraction is
# the expensive part of the pipeline and is deliberately not re-run, since
# this command must not touch sections at all.
PEOPLE_STEPS = [
    PDFExtractionStep,
    LineReconstructionStep,
    PageClassificationStep,
    MetadataFrontMatterStep,
    MetadataPeopleStep,
]


def extract_people(job):
    context = {"start_time": 0, "stop_pipeline": False}
    for step_cls in PEOPLE_STEPS:
        context = step_cls().run(job, context)
    return context.get("draft_metadata", {}).get("people_and_roles", []) or []


class Command(BaseCommand):
    help = (
        "Re-extracts supervisors (and optionally authors) from the original PDFs of "
        "published projects and adds only the people that are currently missing."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be added without writing anything.",
        )
        parser.add_argument(
            "--include-authors",
            action="store_true",
            help="Also add missing Author rows, not just supervisory roles.",
        )
        parser.add_argument(
            "--project-id",
            type=int,
            help="Restrict to a single published project id.",
        )
        parser.add_argument(
            "--all-projects",
            action="store_true",
            help="Include projects that already have at least one supervisor.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        include_authors = options["include_authors"]

        projects = Project.objects.filter(status="Published").order_by("id")
        if options.get("project_id"):
            projects = projects.filter(id=options["project_id"])
            if not projects.exists():
                raise CommandError(
                    f"No published project with id {options['project_id']}."
                )

        if not options["all_projects"]:
            already_supervised = ProjectPerson.objects.filter(
                role__in=SUPERVISORY_ROLES
            ).values_list("project_id", flat=True)
            projects = projects.exclude(id__in=already_supervised)

        projects = list(projects)
        if not projects:
            self.stdout.write("Nothing to do -- no matching published projects.")
            return

        self.stdout.write(
            f"Examining {len(projects)} published project(s)"
            + (" [DRY RUN -- no writes]" if dry_run else "")
        )

        examined = skipped = added_total = 0

        for project in projects:
            job = (
                IngestionJob.objects.filter(published_project=project)
                .exclude(file="")
                .order_by("-created_at")
                .first()
            )
            if job is None or not job.file:
                skipped += 1
                self.stdout.write(
                    f"  SKIP project #{project.id}: no source PDF on record."
                )
                continue

            try:
                people = extract_people(job)
            except Exception as exc:  # noqa: BLE001 -- one bad PDF must not kill the batch
                skipped += 1
                # Only the exception TYPE. Its message routinely embeds the
                # source path, and a report's filename normally repeats its
                # title -- so echoing `exc` here leaked document content
                # into the terminal for every unreadable file.
                self.stderr.write(
                    self.style.ERROR(
                        f"  FAIL project #{project.id}: {type(exc).__name__}"
                    )
                )
                continue

            examined += 1
            added = self._apply(project, people, include_authors, dry_run)
            added_total += len(added)

            if added:
                verb = "would add" if dry_run else "added"
                # Only the roles and how many of each -- the names themselves
                # are extracted document content (students and supervisors)
                # and must not reach a terminal.
                by_role = Counter(role for _name, role in added)
                breakdown = ", ".join(
                    f"{count} x {role}" for role, count in sorted(by_role.items())
                )
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  project #{project.id}: {verb} {len(added)} person link(s) "
                        f"({breakdown})"
                    )
                )
            else:
                self.stdout.write(
                    f"  project #{project.id}: nothing missing to add."
                )

        summary = (
            f"Done. {examined} project(s) re-extracted, {skipped} skipped, "
            f"{added_total} person link(s) "
            + ("that would be added." if dry_run else "added.")
        )
        self.stdout.write(self.style.SUCCESS(summary))

    def _apply(self, project, people, include_authors, dry_run):
        """Adds only the people this project does not already have.

        Existing links are keyed by normalized name so a person already
        recorded under a different role (or with different title
        decoration) is never duplicated -- if the name is present at all,
        it is left exactly as the admin/publish flow recorded it.
        """
        existing_names = {
            pp.person.full_name.strip().lower()
            for pp in project.project_people.select_related("person")
        }

        wanted_roles = set(SUPERVISORY_ROLES)
        if include_authors:
            wanted_roles.add("Author")

        added = []
        for person_data in people:
            role = (person_data.get("role") or "").strip()
            if role not in wanted_roles:
                continue

            raw_name = (person_data.get("full_name") or "").strip()
            if not raw_name:
                continue

            if role == "Author":
                full_name = JobPublishAPIView._normalize_full_name(raw_name)
                title = ""
            else:
                full_name, parsed_title = JobPublishAPIView._parse_faculty_full_name(raw_name)
                title = (person_data.get("title") or "").strip() or parsed_title

            if not full_name:
                continue

            if full_name.strip().lower() in existing_names:
                if role != "Author" and not dry_run:
                    self._fill_blank_faculty_fields(
                        full_name=full_name,
                        title=title,
                        designation=(person_data.get("designation") or "").strip(),
                    )
                continue

            existing_names.add(full_name.strip().lower())
            added.append((full_name, role))

            if dry_run:
                continue

            with transaction.atomic():
                if role == "Author":
                    person = JobPublishAPIView.get_or_create_student(
                        full_name=full_name,
                        department=project.department,
                        roll_number=clean_roll_number(
                            (person_data.get("roll_number") or "").strip()
                        ),
                        academic_level=person_data.get("academic_level") or "UG",
                    )
                else:
                    person = self._resolve_faculty(
                        full_name=full_name,
                        department=project.department,
                        designation=(person_data.get("designation") or "").strip(),
                        title=title,
                    )

                ProjectPerson.objects.get_or_create(
                    project=project,
                    person=person,
                    role=role,
                    defaults={
                        "display_order": project.project_people.count() + 1,
                    },
                )

        return added

    @staticmethod
    def _fill_blank_faculty_fields(*, full_name, title, designation):
        """Tops up empty title/designation on a faculty record that is
        already linked to this project.

        Only blanks are written. A value an administrator corrected by hand
        must survive a backfill, so this can add information but never
        replace it."""
        faculty = Faculty.objects.filter(full_name__iexact=full_name).first()
        if faculty is None:
            return

        fills = {}
        if title and not faculty.title:
            fills["title"] = title
        if designation and not faculty.designation:
            fills["designation"] = designation
        if fills:
            for field, value in fills.items():
                setattr(faculty, field, value)
            faculty.save(update_fields=list(fills))

    @staticmethod
    def _resolve_faculty(*, full_name, department, designation, title):
        """Finds an existing Faculty by name, or creates one.

        Deliberately NOT JobPublishAPIView.get_or_create_faculty: that uses
        `update_or_create`, which would stamp this re-extraction's
        designation/title onto a faculty record that other projects already
        share -- overwriting, for instance, a designation an admin had
        corrected by hand with an empty string. A backfill must not be able
        to degrade data that is already there, so an existing record is
        returned untouched and its blank fields are only filled in when
        this run actually has a value for them.
        """
        faculty = Faculty.objects.filter(full_name__iexact=full_name).first()
        if faculty is None:
            return Faculty.objects.create(
                full_name=full_name,
                department=department,
                designation=designation,
                title=title,
            )

        fills = {}
        if designation and not faculty.designation:
            fills["designation"] = designation
        if title and not faculty.title:
            fills["title"] = title
        if department is not None and faculty.department_id is None:
            fills["department"] = department
        if fills:
            for field, value in fills.items():
                setattr(faculty, field, value)
            faculty.save(update_fields=list(fills))
        return faculty
