"""
Merging bundles from several machines into one database.

The scenario these protect: three people ingest different PDFs on three
local databases, then merge. The failure that matters is not a crash -- it
is a silent duplicate, where the same supervisor arrives from two bundles
and ends up as two records splitting his project list between them.
"""

import json
import tempfile
from io import StringIO
from pathlib import Path

from ingestion.models import IngestionJob

from django.core.management import call_command
from django.test import TestCase

from accounts.models import Faculty, Person, Student
from organization.models import Campus, Department
from repository.models import (
    Keyword,
    Project,
    ProjectKeyword,
    ProjectPerson,
    ProjectSection,
)


def make_bundle(directory, source, projects):
    """Writes a bundle by hand, standing in for another machine's export."""
    root = Path(directory)
    (root / "projects").mkdir(parents=True, exist_ok=True)
    (root / "manifest.json").write_text(
        json.dumps({"bundle_version": 1, "source": source,
                    "project_count": len(projects)}),
        encoding="utf-8",
    )
    for index, record in enumerate(projects, start=1):
        (root / "projects" / f"project_{index:04d}.json").write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )
    return root


def project_record(title, *, batch="078", people=(), keywords=(), sections=()):
    return {
        "identity": f"tb:{title}",
        "fields": {
            "title": title, "abstract": f"Abstract of {title}.",
            "description": "", "project_type": "Major", "academic_level": "UG",
            "batch": batch, "cluster": "AIML", "language": "English",
            "github_url": "", "doi_url": "", "publication_url": "", "demo_url": "",
            "department_name": "Department of Electronics and Computer Engineering",
            "research_group_name": "",
        },
        "people": list(people),
        "sections": list(sections),
        "keywords": list(keywords),
        "domains": [],
        "references": [],
        "job": None,
    }


SUPERVISOR = {
    "full_name": "Bikal Adhikari", "email": "", "role": "Supervisor",
    "display_order": 1, "kind": "faculty",
    "title": "Dr.", "designation": "Associate Professor",
}


def student(name, roll):
    return {
        "full_name": name, "email": "", "role": "Author", "display_order": 2,
        "kind": "student", "roll_number": roll, "academic_level": "UG",
    }


class BundleMergeTests(TestCase):
    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        Department.objects.get_or_create(
            name="Department of Electronics and Computer Engineering", campus=campus
        )

    def merge(self, directory, **kwargs):
        out = StringIO()
        call_command("import_bundle", bundle=str(directory), stdout=out, **kwargs)
        return out.getvalue()

    # ------------------------------------------------------------------

    def test_two_bundles_sharing_a_supervisor_produce_one_record(self):
        """The whole point: no split project list in the search facet."""
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            make_bundle(a, "asha", [
                project_record("Vision system", people=[SUPERVISOR, student("Nischal Karki", "078BEL011")]),
            ])
            make_bundle(b, "bikash", [
                project_record("Mesh routing", people=[SUPERVISOR, student("Rita Thapa", "078BEL012")]),
            ])
            self.merge(a)
            self.merge(b)

        self.assertEqual(Faculty.objects.filter(full_name="Bikal Adhikari").count(), 1)
        supervisor = Faculty.objects.get(full_name="Bikal Adhikari")
        self.assertEqual(
            ProjectPerson.objects.filter(person=supervisor, role="Supervisor").count(), 2
        )
        self.assertEqual(Project.objects.count(), 2)

    def test_importing_the_same_bundle_twice_changes_nothing(self):
        with tempfile.TemporaryDirectory() as a:
            make_bundle(a, "asha", [
                project_record("Vision system", people=[SUPERVISOR, student("Nischal Karki", "078BEL011")],
                               keywords=["machine learning", "traffic"]),
            ])
            self.merge(a)
            counts = (Project.objects.count(), Person.objects.count(),
                      ProjectPerson.objects.count(), Keyword.objects.count())
            self.merge(a)

        self.assertEqual(
            (Project.objects.count(), Person.objects.count(),
             ProjectPerson.objects.count(), Keyword.objects.count()),
            counts,
        )

    def test_a_keyword_used_by_two_people_is_stored_once(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            make_bundle(a, "asha", [project_record("P1", keywords=["machine learning"])])
            make_bundle(b, "bikash", [project_record("P2", keywords=["Machine Learning"])])
            self.merge(a)
            self.merge(b)

        self.assertEqual(Keyword.objects.filter(name__iexact="machine learning").count(), 1)
        self.assertEqual(ProjectKeyword.objects.count(), 2)

    def test_a_student_is_matched_on_roll_number_not_name(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            make_bundle(a, "asha", [project_record("P1", people=[student("Nischal Karki", "078BEL011")])])
            # Same roll, name recorded slightly differently on the other machine.
            make_bundle(b, "bikash", [project_record("P2", people=[student("Nischal  karki", "078BEL011")])])
            self.merge(a)
            self.merge(b)

        self.assertEqual(Student.objects.filter(roll_number="078BEL011").count(), 1)

    def test_a_merge_never_blanks_a_hand_corrected_value(self):
        """An administrator's correction must survive a later import."""
        with tempfile.TemporaryDirectory() as a:
            make_bundle(a, "asha", [project_record("P1", people=[SUPERVISOR])])
            self.merge(a)

            supervisor = Faculty.objects.get(full_name="Bikal Adhikari")
            supervisor.designation = "Professor"   # corrected by hand
            supervisor.save(update_fields=["designation"])

            self.merge(a)

        self.assertEqual(
            Faculty.objects.get(full_name="Bikal Adhikari").designation, "Professor"
        )

    def test_sections_survive_the_round_trip_in_order(self):
        sections = [
            {"heading": "1. Introduction", "canonical_section": "introduction",
             "heading_level": 1, "display_order": 1, "content": "x",
             "page_start": 1, "page_end": 2, "word_count": 1},
            {"heading": "1.1 Background", "canonical_section": "",
             "heading_level": 2, "display_order": 2, "content": "y",
             "page_start": 2, "page_end": 3, "word_count": 1},
        ]
        with tempfile.TemporaryDirectory() as a:
            make_bundle(a, "asha", [project_record("P1", sections=sections)])
            self.merge(a)

        rows = ProjectSection.objects.order_by("display_order")
        self.assertEqual([r.heading for r in rows], ["1. Introduction", "1.1 Background"])
        self.assertEqual([r.heading_level for r in rows], [1, 2])

    def test_a_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as a:
            make_bundle(a, "asha", [project_record("P1", people=[SUPERVISOR])])
            self.merge(a, dry_run=True)

        self.assertEqual(Project.objects.count(), 0)
        self.assertEqual(Faculty.objects.count(), 0)

    def test_the_department_resolves_by_name_without_carrying_an_id(self):
        with tempfile.TemporaryDirectory() as a:
            make_bundle(a, "asha", [project_record("P1")])
            self.merge(a)

        project = Project.objects.get(title="P1")
        self.assertIsNotNone(project.department_id)
        self.assertEqual(
            project.department.name,
            "Department of Electronics and Computer Engineering",
        )

    def test_output_names_no_project_and_no_file(self):
        """Merge output must stay free of document content."""
        with tempfile.TemporaryDirectory() as a:
            make_bundle(a, "asha", [project_record("Secret Vision System")])
            output = self.merge(a)

        self.assertNotIn("Secret Vision System", output)
        self.assertIn("Document #1", output)


class RealMergeWithPdfTests(TestCase):
    """
    A real (non-dry-run) merge of a bundle whose project carries a source
    PDF -- the case a dry run structurally can't exercise, since
    `_attach_pdf` only runs when writes are for real. `uploaded_by` on
    `IngestionJob` is a required field that construction here previously
    never set, which passed every dry run cleanly and then raised
    IntegrityError on every real merge that attached a PDF.
    """

    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        Department.objects.get_or_create(
            name="Department of Electronics and Computer Engineering", campus=campus
        )

    def _bundle_with_pdf(self, directory, *, uploader_email=""):
        root = Path(directory)
        (root / "projects").mkdir(parents=True)
        (root / "pdfs").mkdir(parents=True)
        (root / "manifest.json").write_text(
            json.dumps({"bundle_version": 1, "source": "t", "project_count": 1}),
            encoding="utf-8",
        )
        (root / "pdfs" / "project_0001.pdf").write_bytes(b"%PDF-1.4 fake")
        record = project_record("PDF-carrying project")
        record["pdf"] = "project_0001.pdf"
        record["job"] = {
            "original_filename": "report.pdf", "file_hash": "hash-1",
            "status": "VERIFIED", "extracted_payload": {},
            "uploaded_by_email": uploader_email,
        }
        (root / "projects" / "project_0001.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        return root

    def test_a_real_merge_with_a_pdf_does_not_raise(self):
        with tempfile.TemporaryDirectory() as d:
            self._bundle_with_pdf(d)
            out = StringIO()
            call_command("import_bundle", bundle=d, stdout=out)
            output = out.getvalue()

        self.assertNotIn("IntegrityError", output)
        self.assertIn("projects created....: 1", output)
        job = IngestionJob.objects.get(published_project__title="PDF-carrying project")
        self.assertTrue(job.file)

    def test_the_attached_job_has_a_valid_owner(self):
        with tempfile.TemporaryDirectory() as d:
            self._bundle_with_pdf(d)
            call_command("import_bundle", bundle=d, stdout=StringIO())

        job = IngestionJob.objects.get(published_project__title="PDF-carrying project")
        self.assertIsNotNone(job.uploaded_by_id)

    def test_it_prefers_the_original_uploaders_own_account_when_it_exists_here(self):
        from accounts.models import User
        uploader = User.objects.create_user(email="original@pcampus.edu.np", password="x")

        with tempfile.TemporaryDirectory() as d:
            self._bundle_with_pdf(d, uploader_email="original@pcampus.edu.np")
            call_command("import_bundle", bundle=d, stdout=StringIO())

        job = IngestionJob.objects.get(published_project__title="PDF-carrying project")
        self.assertEqual(job.uploaded_by_id, uploader.id)

    def test_it_falls_back_to_a_system_account_when_the_uploader_is_unknown_here(self):
        with tempfile.TemporaryDirectory() as d:
            self._bundle_with_pdf(d, uploader_email="someone-not-on-this-machine@x.np")
            call_command("import_bundle", bundle=d, stdout=StringIO())

        job = IngestionJob.objects.get(published_project__title="PDF-carrying project")
        self.assertEqual(job.uploaded_by.email, "bundle-merge@local.invalid")

    def test_re_merging_the_same_bundle_does_not_recreate_the_job(self):
        with tempfile.TemporaryDirectory() as d:
            self._bundle_with_pdf(d)
            call_command("import_bundle", bundle=d, stdout=StringIO())
            call_command("import_bundle", bundle=d, stdout=StringIO())

        self.assertEqual(
            IngestionJob.objects.filter(
                published_project__title="PDF-carrying project"
            ).count(),
            1,
        )


class MergedProjectReportAccessTests(TestCase):
    """
    A privileged reviewer must actually see the report after a merge --
    the reported bug: an admin still saw the report as restricted because
    the merge attached the PDF to the job but never created the
    ProjectAsset row the catalogue's access check actually looks at.
    """

    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        Department.objects.get_or_create(
            name="Department of Electronics and Computer Engineering", campus=campus
        )

    def _bundle_with_pdf(self, directory):
        root = Path(directory)
        (root / "projects").mkdir(parents=True)
        (root / "pdfs").mkdir(parents=True)
        (root / "manifest.json").write_text(
            json.dumps({"bundle_version": 1, "source": "t", "project_count": 1}),
            encoding="utf-8",
        )
        (root / "pdfs" / "project_0001.pdf").write_bytes(b"%PDF-1.4 fake")
        record = project_record("Merged report project")
        record["pdf"] = "project_0001.pdf"
        record["job"] = {
            "original_filename": "report.pdf", "file_hash": "hash-2",
            "status": "VERIFIED", "extracted_payload": {}, "uploaded_by_email": "",
        }
        (root / "projects" / "project_0001.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
        return root

    def test_an_admin_sees_the_report_url_after_a_merge(self):
        from django.urls import reverse
        from rest_framework.test import APIClient
        from accounts.models import User

        with tempfile.TemporaryDirectory() as d:
            self._bundle_with_pdf(d)
            call_command("import_bundle", bundle=d, stdout=StringIO())

        project = Project.objects.get(title="Merged report project")
        admin = User.objects.create_user(
            email="admin@pcampus.edu.np", password="x",
            is_staff=True, is_superuser=True, role="admin",
        )
        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.get(reverse("repository:project-detail", args=[project.id]))

        self.assertIsNotNone(response.data["data"]["pdfUrl"])
        self.assertEqual(response.data["data"]["accessStatus"], "granted")

    def test_the_report_asset_row_is_created(self):
        with tempfile.TemporaryDirectory() as d:
            self._bundle_with_pdf(d)
            call_command("import_bundle", bundle=d, stdout=StringIO())

        project = Project.objects.get(title="Merged report project")
        self.assertTrue(project.assets.filter(asset_type="Report").exists())

    def test_re_merging_does_not_duplicate_the_asset(self):
        with tempfile.TemporaryDirectory() as d:
            self._bundle_with_pdf(d)
            call_command("import_bundle", bundle=d, stdout=StringIO())
            call_command("import_bundle", bundle=d, stdout=StringIO())

        project = Project.objects.get(title="Merged report project")
        self.assertEqual(project.assets.filter(asset_type="Report").count(), 1)

    def test_an_ordinary_reader_still_cannot_see_it(self):
        """The fix must not accidentally open access to everyone."""
        from django.urls import reverse
        from rest_framework.test import APIClient
        from accounts.models import User

        with tempfile.TemporaryDirectory() as d:
            self._bundle_with_pdf(d)
            call_command("import_bundle", bundle=d, stdout=StringIO())

        project = Project.objects.get(title="Merged report project")
        reader = User.objects.create_user(email="reader@pcampus.edu.np", password="x")
        client = APIClient()
        client.force_authenticate(user=reader)
        response = client.get(reverse("repository:project-detail", args=[project.id]))

        self.assertIsNone(response.data["data"]["pdfUrl"])
