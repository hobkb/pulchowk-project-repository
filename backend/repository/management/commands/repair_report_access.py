"""Repair report access on projects that arrived through a bundle merge.

A project looks locked even to a superuser because the detail serializer sets
`accessStatus` and `pdfUrl` independently, and the frontend requires both:

    accessStatus === "granted" && Boolean(project.pdfUrl)

`pdfUrl` comes from the project's ProjectAsset row of type "Report". A bundle
merge transfers the project, its sections and its people but not always that
asset row or the file behind it, so the account is fine and the asset is
missing.

For every published project this checks for a usable Report asset and rebuilds
a missing one from the ingestion job that published it, whose own FileField
still holds a recoverable local path. Outcomes:

    ok          asset exists and its file is on disk
    repaired    asset rebuilt from the ingestion job
    no_file     asset or job path exists but the PDF is absent; media files
                still need copying across
    no_source   no linked ingestion job, nothing to rebuild from

Read-only by default; pass --apply to write.

Output is deliberately content-free: only counts, ids, status words, booleans
and byte sizes. Filenames echo project titles, so they are never read into a
printable variable, and exception handlers report the exception class rather
than its message, since a file error embeds the path it failed on.
"""

import json
import mimetypes
import os
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from ingestion.models import IngestionJob
from repository.models import Project, ProjectAsset

REPORT_ASSET_TYPE = "Report"
PDF_MIME = "application/pdf"
MERGE_USER_EMAIL = "bundle-merge@local.invalid"


class Command(BaseCommand):
    help = "Rebuild missing Report assets so administrators can open reports."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write the repairs. Without it the command only reports.",
        )
        parser.add_argument(
            "--project-id",
            type=str,
            default=None,
            help="Limit the run to a single project id.",
        )
        parser.add_argument(
            "--from-bundle",
            type=str,
            action="append",
            default=[],
            dest="bundles",
            help=(
                "Path to an unpacked bundle directory to recover PDFs from. "
                "Repeat for several bundles. Use this for projects reported "
                "as 'no ingestion job linked': the bundle still holds the "
                "PDF and the hash needed to match it to a project."
            ),
        )
        parser.add_argument(
            "--scan-media",
            action="store_true",
            help=(
                "Fallback for bundle records whose PDF was left out of the "
                "export. Hashes every PDF already under media/ingestion_pdfs "
                "and matches by SHA-256, the same digest the pipeline "
                "records, so no filename or title is involved."
            ),
        )
        parser.add_argument(
            "--check-user",
            type=str,
            default=None,
            help=(
                "Also report the privilege flags of this account. Use it when "
                "a project is fine but one particular administrator still "
                "sees the request button."
            ),
        )

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _stored_path(file_field):
        """Absolute path of a FileField, or None. The path is used for an
        existence test only and is never returned to the caller for printing."""
        if not file_field or not file_field.name:
            return None
        try:
            return file_field.path
        except (ValueError, NotImplementedError):
            return None

    @classmethod
    def _file_present(cls, file_field):
        path = cls._stored_path(file_field)
        return bool(path) and os.path.isfile(path)

    @classmethod
    def _size_of(cls, file_field):
        path = cls._stored_path(file_field)
        if not path or not os.path.isfile(path):
            return 0
        try:
            return os.path.getsize(path)
        except OSError:
            return 0

    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        apply_changes = options["apply"]
        project_id = options["project_id"]
        check_user = options["check_user"]
        bundles = options["bundles"]

        # Bundle recovery runs first, so that anything it restores is then
        # counted as usable by the pass below rather than being reported as
        # broken in the same run.
        if bundles:
            self._media_index = (
                self._build_media_index() if options["scan_media"] else None
            )
            self._recover_from_bundles(bundles, apply_changes)

        projects = Project.objects.all().order_by("created_at")
        if project_id:
            projects = projects.filter(id=project_id)

        counts = {"ok": 0, "repaired": 0, "no_file": 0, "no_source": 0}
        detail = {"repaired": [], "no_file": [], "no_source": []}

        for project in projects:
            outcome = self._inspect_and_repair(project, apply_changes)
            counts[outcome] += 1
            if outcome != "ok":
                detail[outcome].append(str(project.id))

        self._report(counts, detail, apply_changes)

        if check_user:
            self._report_user(check_user)

    # ------------------------------------------------------------------
    def _inspect_and_repair(self, project, apply_changes):
        asset = (
            ProjectAsset.objects.filter(project=project, asset_type=REPORT_ASSET_TYPE)
            .order_by("uploaded_at")
            .first()
        )

        if asset is not None and self._file_present(asset.file):
            return "ok"

        # Either there is no asset row at all, or there is one whose file is
        # empty or absent from disk. In both cases the ingestion job is the
        # only local source of the PDF path.
        job = (
            IngestionJob.objects.filter(published_project=project)
            .exclude(file="")
            .order_by("-created_at")
            .first()
        )
        if job is None:
            return "no_source"

        if not self._file_present(job.file):
            # The row can be rebuilt but the bytes are not on this machine, so
            # rebuilding it would only produce a link that 404s.
            return "no_file"

        if not apply_changes:
            return "repaired"

        try:
            with transaction.atomic():
                if asset is None:
                    ProjectAsset.objects.create(
                        project=project,
                        asset_type=REPORT_ASSET_TYPE,
                        file=job.file.name,
                        mime_type=PDF_MIME,
                        file_size=self._size_of(job.file),
                    )
                else:
                    asset.file = job.file.name
                    asset.mime_type = asset.mime_type or PDF_MIME
                    asset.file_size = self._size_of(job.file)
                    asset.save(update_fields=["file", "mime_type", "file_size"])
        except Exception as exc:  # noqa: BLE001
            # The message of a file or database error embeds the path it
            # failed on, so only the exception class is reported.
            self.stderr.write(
                "  project %s: repair failed (%s)" % (project.id, type(exc).__name__)
            )
            return "no_file"

        return "repaired"

    # ------------------------------------------------------------------
    def _report(self, counts, detail, apply_changes):
        mode = "APPLIED" if apply_changes else "DRY RUN (no changes written)"
        total = sum(counts.values())

        self.stdout.write("")
        self.stdout.write("Report access repair -- %s" % mode)
        self.stdout.write("-" * 52)
        self.stdout.write("  projects examined         : %d" % total)
        self.stdout.write("  already usable            : %d" % counts["ok"])
        self.stdout.write(
            "  %-25s : %d"
            % ("repaired" if apply_changes else "repairable", counts["repaired"])
        )
        self.stdout.write("  PDF missing on this machine: %d" % counts["no_file"])
        self.stdout.write("  no ingestion job linked   : %d" % counts["no_source"])

        for key, heading in (
            ("repaired", "repairable / repaired"),
            ("no_file", "PDF missing on this machine"),
            ("no_source", "no ingestion job linked"),
        ):
            ids = detail[key]
            if not ids:
                continue
            self.stdout.write("")
            self.stdout.write("  %s -- project ids:" % heading)
            for i in range(0, len(ids), 4):
                self.stdout.write("    " + "  ".join(ids[i : i + 4]))

        self.stdout.write("")
        if counts["repaired"] and not apply_changes:
            self.stdout.write("Re-run with --apply to write these repairs.")
        if counts["no_file"]:
            self.stdout.write(
                "Projects counted under 'PDF missing' need the media files "
                "copied into media/ingestion_pdfs/ from the machine that "
                "ingested them; the database row alone is not enough."
            )
        if counts["no_source"]:
            self.stdout.write(
                "Projects counted under 'no ingestion job linked' were "
                "published on another machine and their job did not travel "
                "with the bundle. Re-export that bundle including its jobs, "
                "or attach the report through the admin interface."
            )
        self.stdout.write("")

    # ------------------------------------------------------------------
    # bundle recovery
    # ------------------------------------------------------------------
    def _recover_from_bundles(self, bundle_paths, apply_changes):
        """Restore the PDF for projects whose ingestion job never arrived.

        A bundle carries the source PDF and, for each project, the content
        hash plus the title and batch. That is enough to match a bundle
        record to a local project by exactly the rule import_bundle uses,
        and then to attach the file the same way its own _attach_pdf does.

        Only the file is restored. Metadata is deliberately left alone: the
        catalogue has been corrected by hand since the merge, and a second
        pass over the fields would undo those corrections.
        """
        stats = {"records": 0, "matched": 0, "attached": 0, "already_ok": 0,
                 "unmatched": 0, "no_pdf_in_bundle": 0, "from_media": 0,
                 "failed": 0}

        for raw in bundle_paths:
            bundle = Path(raw)
            project_dir = bundle / "projects"
            if not project_dir.is_dir():
                self.stderr.write("  skipped a path with no projects/ directory")
                continue

            for record_file in sorted(project_dir.glob("*.json")):
                stats["records"] += 1
                try:
                    record = json.loads(record_file.read_text(encoding="utf-8"))
                except Exception as exc:  # noqa: BLE001
                    stats["failed"] += 1
                    self.stderr.write("  unreadable record (%s)" % type(exc).__name__)
                    continue

                project = self._match_project(record)
                if project is None:
                    stats["unmatched"] += 1
                    continue
                stats["matched"] += 1

                asset = ProjectAsset.objects.filter(
                    project=project, asset_type=REPORT_ASSET_TYPE
                ).first()
                if asset is not None and self._file_present(asset.file):
                    stats["already_ok"] += 1
                    continue

                job_data = record.get("job") or {}
                pdf_name = record.get("pdf")
                source = bundle / "pdfs" / pdf_name if pdf_name else None

                if source is None or not source.is_file():
                    # The export left this PDF out. It may still be sitting in
                    # media/ingestion_pdfs from a copied media folder, so fall
                    # back to matching by content hash.
                    existing = self._find_in_media(job_data.get("file_hash"))
                    if existing is None:
                        stats["no_pdf_in_bundle"] += 1
                        continue
                    if not apply_changes:
                        stats["from_media"] += 1
                        continue
                    if self._attach(project, None, job_data, existing):
                        stats["from_media"] += 1
                    else:
                        stats["failed"] += 1
                    continue

                if not apply_changes:
                    stats["attached"] += 1
                    continue

                if self._attach(project, source, job_data, pdf_name):
                    stats["attached"] += 1
                else:
                    stats["failed"] += 1

        self._report_bundles(stats, apply_changes)

    def _match_project(self, record):
        """Same rule import_bundle uses: content hash first, then title and
        batch. Neither value is ever printed."""
        job_data = record.get("job") or {}
        file_hash = job_data.get("file_hash")
        if file_hash:
            job = (
                IngestionJob.objects.filter(file_hash=file_hash)
                .exclude(published_project=None)
                .first()
            )
            if job is not None:
                return job.published_project

        fields = record.get("fields") or {}
        return Project.objects.filter(
            title__iexact=(fields.get("title") or "").strip(),
            batch=fields.get("batch") or "",
        ).first()

    def _build_media_index(self):
        """SHA-256 of every PDF under media/ingestion_pdfs, mapped to its
        storage-relative name. Built once per run."""
        from django.conf import settings

        root = Path(settings.MEDIA_ROOT) / "ingestion_pdfs"
        index = {}
        if not root.is_dir():
            self.stderr.write("  media/ingestion_pdfs not found; scan skipped")
            return index

        import hashlib

        scanned = 0
        for path in root.iterdir():
            if not path.is_file() or path.suffix.lower() != ".pdf":
                continue
            digest = hashlib.sha256()
            try:
                with path.open("rb") as handle:
                    for block in iter(lambda h=handle: h.read(65536), b""):
                        digest.update(block)
            except OSError:
                continue
            # First writer wins: duplicates of the same bytes are equivalent.
            index.setdefault(digest.hexdigest(), "ingestion_pdfs/" + path.name)
            scanned += 1

        self.stdout.write("  media scan: hashed %d PDFs" % scanned)
        return index

    def _find_in_media(self, file_hash):
        if not file_hash or not getattr(self, "_media_index", None):
            return None
        return self._media_index.get(file_hash)

    def _attach(self, project, source, job_data, pdf_name):
        """Mirrors import_bundle._attach_pdf: job first, then the asset row
        that get_pdfUrl actually looks for.

        `source` is a path to copy in, or None when the file is already under
        MEDIA_ROOT. In that case `pdf_name` is its storage-relative name and
        it is referenced in place rather than copied, so a repair run does not
        duplicate half a gigabyte of PDFs.
        """
        try:
            with transaction.atomic():
                job = IngestionJob.objects.filter(published_project=project).first()
                if job is None:
                    job = IngestionJob(
                        published_project=project,
                        original_filename=job_data.get("original_filename")
                        or os.path.basename(pdf_name),
                        file_hash=job_data.get("file_hash") or "",
                        status=job_data.get("status") or IngestionJob.Status.VERIFIED,
                        extracted_payload=job_data.get("extracted_payload") or {},
                        uploaded_by=self._merge_user(job_data),
                    )
                if not job.file:
                    if source is None:
                        job.file.name = pdf_name
                    else:
                        with source.open("rb") as handle:
                            job.file.save(pdf_name, File(handle), save=False)
                job.save()

                if not project.assets.filter(asset_type=REPORT_ASSET_TYPE).exists():
                    mime_type, _ = mimetypes.guess_type(job.file.name)
                    ProjectAsset.objects.create(
                        project=project,
                        asset_type=REPORT_ASSET_TYPE,
                        file=job.file.name,
                        mime_type=mime_type or PDF_MIME,
                        file_size=self._size_of(job.file),
                    )
            return True
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(
                "  project %s: attach failed (%s)" % (project.id, type(exc).__name__)
            )
            return False

    @staticmethod
    def _merge_user(job_data):
        """The original uploader if that account exists here, else the same
        placeholder account import_bundle uses, so a repair run does not
        introduce a second system user."""
        user_model = get_user_model()
        email = (job_data.get("uploaded_by_email") or "").strip()
        if email:
            existing = user_model.objects.filter(email__iexact=email).first()
            if existing is not None:
                return existing
        user, created = user_model.objects.get_or_create(
            email=MERGE_USER_EMAIL,
            defaults={"first_name": "Bundle", "last_name": "Merge"},
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        return user

    def _report_bundles(self, s, apply_changes):
        verb = "attached" if apply_changes else "recoverable"
        self.stdout.write("")
        self.stdout.write("Bundle recovery")
        self.stdout.write("-" * 52)
        self.stdout.write("  bundle records read       : %d" % s["records"])
        self.stdout.write("  matched to a local project: %d" % s["matched"])
        self.stdout.write("  already had a usable PDF  : %d" % s["already_ok"])
        self.stdout.write("  %-25s : %d" % (verb + " from bundle", s["attached"]))
        self.stdout.write("  %-25s : %d" % (verb + " from media", s["from_media"]))
        self.stdout.write("  PDF found nowhere         : %d" % s["no_pdf_in_bundle"])
        self.stdout.write("  no matching local project : %d" % s["unmatched"])
        if s["failed"]:
            self.stdout.write("  failed                    : %d" % s["failed"])

    # ------------------------------------------------------------------
    def _report_user(self, email):
        user_model = get_user_model()
        user = user_model.objects.filter(email__iexact=email).first()

        self.stdout.write("Account privilege check")
        self.stdout.write("-" * 52)
        if user is None:
            self.stdout.write("  no account found for the address supplied")
            self.stdout.write("")
            return

        from organization.models import DepartmentAdmin

        person_id = getattr(user, "person_id", None)
        # Same filter the serializer applies, so this diagnostic cannot
        # disagree with the gate it is explaining.
        dept_admin = (
            DepartmentAdmin.objects.filter(
                faculty_id=person_id, is_active=True
            ).exists()
            if person_id
            else False
        )
        privileged = bool(
            user.is_staff
            or user.is_superuser
            or getattr(user, "role", None) == "admin"
            or dept_admin
        )

        self.stdout.write("  is_staff                  : %s" % user.is_staff)
        self.stdout.write("  is_superuser              : %s" % user.is_superuser)
        self.stdout.write("  role == admin             : %s" % (getattr(user, "role", None) == "admin"))
        self.stdout.write("  active department admin   : %s" % dept_admin)
        self.stdout.write("  counts as reviewer        : %s" % privileged)
        if not privileged:
            self.stdout.write("")
            self.stdout.write(
                "  This account is not a reviewer, so every report shows the "
                "request button regardless of the asset rows. Grant the role "
                "through the role request queue, or set the flags directly."
            )
        self.stdout.write("")
