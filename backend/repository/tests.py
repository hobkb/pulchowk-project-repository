from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Faculty, Student, User
from ingestion.models import IngestionJob
from organization.models import Campus, Department
from notifications.models import Notification
from repository.models import (
    Bookmark,
    Keyword,
    ProjectAccessRequest,
    ProjectAsset,
    Project,
    ProjectKeyword,
    ProjectPerson,
    ProjectSection,
)
from repository.serializers import build_section_tree


class SectionTreeReconstructionTests(TestCase):
    """
    The published document's hierarchy is rebuilt from the flat
    ProjectSection rows using document order + heading_level. These cover
    the reconstruction rule itself, independent of the database.
    """

    @staticmethod
    def _rows(*pairs):
        return [
            {"heading": heading, "heading_level": level, "display_order": order}
            for order, (heading, level) in enumerate(pairs, start=1)
        ]

    def test_children_nest_under_their_parent(self):
        tree = build_section_tree(
            self._rows(
                ("Introduction", 1),
                ("1.1 Background", 2),
                ("1.2 Problem Statement", 2),
                ("Literature Review", 1),
                ("2.1 Previous Work", 2),
            )
        )

        self.assertEqual([n["heading"] for n in tree], ["Introduction", "Literature Review"])
        self.assertEqual(
            [c["heading"] for c in tree[0]["children"]],
            ["1.1 Background", "1.2 Problem Statement"],
        )
        self.assertEqual([c["heading"] for c in tree[1]["children"]], ["2.1 Previous Work"])

    def test_arbitrary_depth_is_preserved(self):
        tree = build_section_tree(
            self._rows(
                ("1 Introduction", 1),
                ("1.1 Background", 2),
                ("1.1.1 Historical Background", 3),
                ("1.1.2 Technical Background", 3),
                ("1.2 Problem Statement", 2),
                ("2 Literature Review", 1),
            )
        )

        self.assertEqual(len(tree), 2)
        background = tree[0]["children"][0]
        self.assertEqual(background["heading"], "1.1 Background")
        self.assertEqual(
            [c["heading"] for c in background["children"]],
            ["1.1.1 Historical Background", "1.1.2 Technical Background"],
        )
        self.assertEqual(tree[0]["children"][1]["heading"], "1.2 Problem Statement")
        self.assertEqual(tree[0]["children"][1]["children"], [])

    def test_impossible_level_gap_is_clamped_not_dropped(self):
        # A level-3 heading with no level-2 open must still appear.
        tree = build_section_tree(self._rows(("Introduction", 1), ("Orphan", 3)))

        self.assertEqual(len(tree), 1)
        self.assertEqual(len(tree[0]["children"]), 1)
        self.assertEqual(tree[0]["children"][0]["heading"], "Orphan")
        self.assertEqual(tree[0]["children"][0]["heading_level"], 2)

    def test_no_sections_yields_empty_tree(self):
        self.assertEqual(build_section_tree([]), [])


class PublishedSectionOrderingTests(TestCase):
    """
    End-to-end: publishing a job whose payload carries a nested tree must
    produce rows that read back in document order and rebuild into the
    same hierarchy. Regression cover for the display_order collision --
    the tree numbers each node within its own parent, so "1.1" and
    "2 Literature Review" both arrived as display_order=1 and the
    published document came back interleaved.
    """

    def setUp(self):
        self.campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.department = Department.objects.create(
            name="Computer Engineering", campus=self.campus
        )
        self.admin = User.objects.create_user(
            email="secordering-admin@example.com", password="secret123", is_staff=True
        )
        self.uploader = User.objects.create_user(
            email="secordering-uploader@example.com", password="secret123"
        )

    def _publish_with_sections(self, sections):
        job = IngestionJob.objects.create(
            file=SimpleUploadedFile("r.pdf", b"%PDF-1.4", content_type="application/pdf"),
            original_filename="r.pdf",
            uploaded_by=self.uploader,
            status=IngestionJob.Status.EXTRACTED,
            extracted_payload={
                "project_fields": {
                    "title": "Hierarchy Test Project",
                    "abstract": "Abstract.",
                    "department_name": self.department.name,
                    "campus_name": self.campus.name,
                },
                "people_and_roles": [{"full_name": "Alice Example", "role": "Author"}],
                "project_sections": sections,
            },
        )
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.post(reverse("ingestion:job-publish", args=[job.id]))
        self.assertEqual(response.status_code, 200, response.data)
        job.refresh_from_db()
        return job.published_project

    def test_document_order_and_hierarchy_survive_publishing(self):
        project = self._publish_with_sections(
            [
                {
                    "heading": "Introduction",
                    "heading_level": 1,
                    "display_order": 1,
                    "content": "Intro body.",
                    "children": [
                        {"heading": "1.1 Background", "heading_level": 2, "display_order": 1, "content": "a", "children": []},
                        {"heading": "1.2 Problem Statement", "heading_level": 2, "display_order": 2, "content": "b", "children": []},
                    ],
                },
                {
                    "heading": "Literature Review",
                    "heading_level": 1,
                    "display_order": 2,
                    "content": "Lit body.",
                    "children": [
                        {"heading": "2.1 Previous Work", "heading_level": 2, "display_order": 1, "content": "c", "children": []},
                    ],
                },
            ]
        )

        headings = list(
            ProjectSection.objects.filter(project=project)
            .order_by("display_order")
            .values_list("heading", flat=True)
        )
        self.assertEqual(
            headings,
            [
                "Introduction",
                "1.1 Background",
                "1.2 Problem Statement",
                "Literature Review",
                "2.1 Previous Work",
            ],
        )

        orders = list(
            ProjectSection.objects.filter(project=project).values_list(
                "display_order", flat=True
            )
        )
        self.assertEqual(len(orders), len(set(orders)), "display_order must be unique")

        # The report body is only served to reviewers, so the hierarchy is
        # asserted through an authenticated admin request.
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.get(reverse("repository:project-detail", args=[project.id]))
        self.assertEqual(response.status_code, 200)
        sections = response.data["data"]["sections"]

        self.assertEqual([s["heading"] for s in sections], ["Introduction", "Literature Review"])
        self.assertEqual(
            [c["heading"] for c in sections[0]["children"]],
            ["1.1 Background", "1.2 Problem Statement"],
        )
        self.assertEqual([c["heading"] for c in sections[1]["children"]], ["2.1 Previous Work"])

    def test_missing_heading_level_falls_back_to_nesting_depth(self):
        project = self._publish_with_sections(
            [
                {
                    "heading": "Methodology",
                    "display_order": 1,
                    "content": "m",
                    "children": [
                        {"heading": "System Design", "display_order": 1, "content": "s", "children": []},
                    ],
                }
            ]
        )

        levels = dict(
            ProjectSection.objects.filter(project=project).values_list(
                "heading", "heading_level"
            )
        )
        self.assertEqual(levels["Methodology"], 1)
        self.assertEqual(levels["System Design"], 2)


class ProjectSearchTests(TestCase):
    """Keyword search is plain case-insensitive substring matching over
    real stored columns -- these pin down the multi-term AND behaviour and
    the fields it reaches across."""

    def setUp(self):
        self.campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.electronics = Department.objects.create(
            name="Electronics Engineering", campus=self.campus
        )
        self.civil = Department.objects.create(name="Civil Engineering", campus=self.campus)

        self.tracker = Project.objects.create(
            title="Dual-axis tracker for solar arrays",
            abstract="A microcontroller driven mount.",
            project_type="Major",
            academic_level="UG",
            batch="078",
            status="Published",
            department=self.electronics,
        )
        self.bridge = Project.objects.create(
            title="Suspension bridge load analysis",
            abstract="Finite element study of a footbridge.",
            project_type="Thesis",
            academic_level="Masters",
            batch="077",
            status="Published",
            department=self.civil,
        )
        self.draft = Project.objects.create(
            title="Unpublished solar study",
            abstract="Should never appear.",
            project_type="Major",
            academic_level="UG",
            status="Processing",
            department=self.electronics,
        )

        student = Student.objects.create(
            full_name="Nischal Karki", roll_number="078BEL011", academic_level="UG"
        )
        ProjectPerson.objects.create(
            project=self.tracker, person=student, role="Author", display_order=1
        )
        supervisor = Faculty.objects.create(
            full_name="Bikal Adhikari", department=self.electronics
        )
        ProjectPerson.objects.create(
            project=self.tracker, person=supervisor, role="Supervisor", display_order=2
        )
        keyword = Keyword.objects.create(name="photovoltaics")
        ProjectKeyword.objects.create(project=self.tracker, keyword=keyword)

    def _search(self, **params):
        response = APIClient().get(reverse("repository:project-list"), params)
        self.assertEqual(response.status_code, 200)
        return [p["title"] for p in response.data["data"]]

    def test_empty_query_returns_full_published_catalogue(self):
        titles = self._search()
        self.assertCountEqual(
            titles,
            ["Dual-axis tracker for solar arrays", "Suspension bridge load analysis"],
        )

    def test_unpublished_projects_are_never_returned(self):
        self.assertNotIn("Unpublished solar study", self._search(q="solar"))

    def test_terms_may_match_different_fields(self):
        # "solar" is in the title, "photovoltaics" is a keyword -- neither
        # record contains both words in any single field.
        self.assertEqual(
            self._search(q="solar photovoltaics"),
            ["Dual-axis tracker for solar arrays"],
        )

    def test_terms_need_not_be_adjacent(self):
        self.assertEqual(
            self._search(q="solar tracker"), ["Dual-axis tracker for solar arrays"]
        )

    def test_all_terms_must_match(self):
        self.assertEqual(self._search(q="solar bridge"), [])

    def test_search_matches_author_and_supervisor_names(self):
        self.assertEqual(self._search(q="Nischal"), ["Dual-axis tracker for solar arrays"])
        self.assertEqual(self._search(q="Adhikari"), ["Dual-axis tracker for solar arrays"])

    def test_no_duplicate_rows_when_several_relations_match(self):
        self.assertEqual(len(self._search(q="Karki")), 1)

    def test_department_and_level_filters(self):
        self.assertEqual(
            self._search(department="Civil Engineering"),
            ["Suspension bridge load analysis"],
        )
        self.assertEqual(
            self._search(academic_level="Masters"), ["Suspension bridge load analysis"]
        )
        self.assertEqual(
            self._search(batch="078"), ["Dual-axis tracker for solar arrays"]
        )

    def test_search_and_filter_combine(self):
        self.assertEqual(self._search(q="solar", department="Civil Engineering"), [])

    def test_no_match_returns_empty_list(self):
        self.assertEqual(self._search(q="quantum cryptography"), [])


class ProjectFacetsTests(TestCase):
    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.department = Department.objects.create(
            name="Computer Engineering", campus=campus
        )
        for i in range(2):
            Project.objects.create(
                title=f"Published {i}",
                abstract="a",
                project_type="Major",
                academic_level="UG",
                batch="078",
                status="Published",
                department=self.department,
            )
        Project.objects.create(
            title="Hidden",
            abstract="a",
            project_type="Major",
            academic_level="UG",
            batch="079",
            status="Processing",
            department=self.department,
        )

    def test_facets_count_only_published_projects(self):
        response = APIClient().get(reverse("repository:project-facets"))
        self.assertEqual(response.status_code, 200)
        data = response.data["data"]

        self.assertEqual(data["total"], 2)
        self.assertEqual(
            data["departments"], [{"name": "Computer Engineering", "count": 2}]
        )
        self.assertEqual(data["batches"], [{"name": "078", "count": 2}])
        self.assertEqual(data["academic_levels"], [{"name": "UG", "count": 2}])


class ReportConfidentialityTests(TestCase):
    """
    The report body (extracted sections, references, results summary) is
    confidential and must only reach reviewers. Enforced in the serializer,
    because withholding it in the interface alone would leave it readable
    straight from the API.
    """

    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.department = Department.objects.create(
            name="Electronics Engineering", campus=campus
        )
        self.project = Project.objects.create(
            title="Confidential Body Project",
            abstract="This abstract is public.",
            project_type="Major",
            academic_level="UG",
            batch="078",
            status="Published",
            department=self.department,
        )
        ProjectSection.objects.create(
            project=self.project,
            heading="Introduction",
            canonical_section="Introduction",
            heading_level=1,
            display_order=1,
            content="SECRET BODY TEXT",
        )
        ProjectSection.objects.create(
            project=self.project,
            heading="Results",
            canonical_section="Results",
            heading_level=1,
            display_order=2,
            content="SECRET RESULTS TEXT",
        )
        self.project.references.create(citation="SECRET CITATION")

    def _detail(self, user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user=user)
        response = client.get(
            reverse("repository:project-detail", args=[self.project.id])
        )
        self.assertEqual(response.status_code, 200)
        return response

    def test_anonymous_gets_abstract_but_no_report_body(self):
        response = self._detail()
        data = response.data["data"]

        self.assertEqual(data["abstract"], "This abstract is public.")
        self.assertEqual(data["sections"], [])
        self.assertEqual(data["references"], [])
        self.assertEqual(data["resultsSummary"], "")
        self.assertTrue(data["sections_restricted"])
        self.assertNotIn("SECRET", response.content.decode())

    def test_ordinary_signed_in_user_also_gets_no_report_body(self):
        student = User.objects.create_user(email="reader@example.com", password="secret123")
        response = self._detail(student)

        self.assertEqual(response.data["data"]["sections"], [])
        self.assertTrue(response.data["data"]["sections_restricted"])
        self.assertNotIn("SECRET", response.content.decode())

    def test_admin_receives_the_full_report_body(self):
        admin = User.objects.create_user(
            email="reviewer@example.com", password="secret123", is_staff=True
        )
        response = self._detail(admin)
        data = response.data["data"]

        self.assertFalse(data["sections_restricted"])
        self.assertEqual([s["heading"] for s in data["sections"]], ["Introduction", "Results"])
        self.assertEqual(data["sections"][0]["content"], "SECRET BODY TEXT")
        self.assertEqual(len(data["references"]), 1)

    def test_department_admin_receives_the_full_report_body(self):
        faculty = Faculty.objects.create(full_name="Dept Head", department=self.department)
        user = User.objects.create_user(
            email="depthead@example.com", password="secret123", person=faculty
        )
        from organization.models import DepartmentAdmin

        DepartmentAdmin.objects.create(
            faculty=faculty, department=self.department, is_active=True
        )

        data = self._detail(user).data["data"]
        self.assertFalse(data["sections_restricted"])
        self.assertEqual(len(data["sections"]), 2)

    def test_list_endpoint_never_leaks_section_text_to_the_public(self):
        response = APIClient().get(reverse("repository:project-list"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("SECRET", response.content.decode())
        self.assertEqual(response.data["data"][0]["resultsSummary"], "")

    def test_pdf_url_is_withheld_from_ordinary_users(self):
        self.assertIsNone(self._detail().data["data"]["pdfUrl"])


class BookmarkAPITests(TestCase):
    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        department = Department.objects.create(name="Computer Engineering", campus=campus)
        self.project = Project.objects.create(
            title="Saveable Project",
            abstract="a",
            project_type="Major",
            academic_level="UG",
            status="Published",
            department=department,
        )
        self.unpublished = Project.objects.create(
            title="Draft Project",
            abstract="a",
            project_type="Major",
            academic_level="UG",
            status="Processing",
            department=department,
        )
        self.user_a = User.objects.create_user(email="ba@example.com", password="secret123")
        self.user_b = User.objects.create_user(email="bb@example.com", password="secret123")

    def _client(self, user):
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def test_requires_authentication(self):
        response = APIClient().get(reverse("repository:bookmark-list-create"))
        self.assertIn(response.status_code, (401, 403))

    def test_save_then_list_then_remove(self):
        client = self._client(self.user_a)
        url = reverse("repository:bookmark-list-create")

        created = client.post(url, {"project": self.project.id})
        self.assertEqual(created.status_code, 201)

        listed = client.get(url)
        self.assertEqual([p["title"] for p in listed.data["data"]], ["Saveable Project"])

        detail = reverse("repository:bookmark-detail", args=[self.project.id])
        self.assertTrue(client.get(detail).data["data"]["bookmarked"])

        self.assertEqual(client.delete(detail).status_code, 200)
        self.assertEqual(client.get(url).data["data"], [])

    def test_saving_twice_is_idempotent(self):
        client = self._client(self.user_a)
        url = reverse("repository:bookmark-list-create")
        client.post(url, {"project": self.project.id})
        second = client.post(url, {"project": self.project.id})

        self.assertEqual(second.status_code, 200)
        self.assertEqual(Bookmark.objects.filter(user=self.user_a).count(), 1)

    def test_users_cannot_see_each_others_saved_projects(self):
        self._client(self.user_a).post(
            reverse("repository:bookmark-list-create"), {"project": self.project.id}
        )
        listed = self._client(self.user_b).get(reverse("repository:bookmark-list-create"))
        self.assertEqual(listed.data["data"], [])

    def test_unpublished_project_cannot_be_saved(self):
        response = self._client(self.user_a).post(
            reverse("repository:bookmark-list-create"), {"project": self.unpublished.id}
        )
        self.assertEqual(response.status_code, 404)

class ClusterAndSupervisorFilterTests(TestCase):
    """
    Cluster is a real, validated column on Project; supervisor filtering
    goes through the supervisory roles only. Both combine with the existing
    filters rather than replacing them.
    """

    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.dept = Department.objects.create(name="Electronics Engineering", campus=campus)

        self.sup_a = Faculty.objects.create(
            full_name="Bikal Adhikari",
            department=self.dept,
            title="Dr.",
            designation="Assistant Professor",
        )
        self.sup_b = Faculty.objects.create(full_name="Rita Shakya", department=self.dept)

        self.aiml = self._project("Vision system", "AIML", "078", "UG", self.sup_a)
        self.nts = self._project("Mesh routing", "NTS", "078", "UG", self.sup_b)
        self.aiml_masters = self._project("Speech model", "AIML", "077", "Masters", self.sup_a)
        # Predates the cluster field entirely.
        self.legacy = self._project("Legacy record", None, "076", "UG", None)

    def _project(self, title, cluster, batch, level, supervisor):
        project = Project.objects.create(
            title=title,
            abstract="a",
            project_type="Major",
            academic_level=level,
            batch=batch,
            status="Published",
            department=self.dept,
            cluster=cluster,
        )
        author = Student.objects.create(
            full_name=f"Author {title}",
            roll_number=f"R{Project.objects.count():03d}",
            academic_level="UG",
        )
        ProjectPerson.objects.create(project=project, person=author, role="Author", display_order=1)
        if supervisor:
            ProjectPerson.objects.create(
                project=project, person=supervisor, role="Supervisor", display_order=2
            )
        return project

    def _titles(self, **params):
        response = APIClient().get(reverse("repository:project-list"), params)
        self.assertEqual(response.status_code, 200)
        return [p["title"] for p in response.data["data"]]

    def test_filter_by_cluster(self):
        self.assertCountEqual(self._titles(cluster="AIML"), ["Vision system", "Speech model"])
        self.assertEqual(self._titles(cluster="NTS"), ["Mesh routing"])

    def test_filter_by_supervisor_uses_supervisory_roles_only(self):
        self.assertCountEqual(
            self._titles(supervisor="Bikal Adhikari"), ["Vision system", "Speech model"]
        )
        # An author is never treated as a supervisor.
        self.assertEqual(self._titles(supervisor="Author Vision system"), [])

    def test_filters_combine(self):
        self.assertEqual(self._titles(cluster="AIML", academic_level="UG"), ["Vision system"])
        self.assertEqual(
            self._titles(cluster="AIML", supervisor="Bikal Adhikari", batch="077"),
            ["Speech model"],
        )
        self.assertEqual(self._titles(cluster="NTS", supervisor="Bikal Adhikari"), [])

    def test_project_without_a_cluster_still_lists(self):
        self.assertIn("Legacy record", self._titles())

    def test_cluster_is_returned_by_the_api(self):
        response = APIClient().get(reverse("repository:project-detail", args=[self.aiml.id]))
        self.assertEqual(response.data["data"]["cluster"], "AIML")

    def test_facets_expose_clusters_supervisors_and_the_vocabulary(self):
        data = APIClient().get(reverse("repository:project-facets")).data["data"]

        self.assertEqual(
            data["clusters"], [{"name": "AIML", "count": 2}, {"name": "NTS", "count": 1}]
        )
        # `name` stays the bare name because that is what the supervisor
        # filter matches on; rank travels alongside it for display.
        self.assertCountEqual(
            data["supervisors"],
            [
                {
                    "name": "Bikal Adhikari",
                    "count": 2,
                    "title": "Dr.",
                    "designation": "Assistant Professor",
                },
                {"name": "Rita Shakya", "count": 1, "title": "", "designation": ""},
            ],
        )
        # Filtering still works on the plain name, not the decorated one.
        self.assertCountEqual(
            self._titles(supervisor="Bikal Adhikari"), ["Vision system", "Speech model"]
        )
        self.assertEqual(
            data["cluster_choices"],
            ["AIML", "ANLP", "NTS", "EII", "EDMES", "ACOM", "IPCV"],
        )


class ClusterValidationTests(TestCase):
    """The cluster vocabulary is enforced on the way in, not just in the UI."""

    def setUp(self):
        self.campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.department = Department.objects.create(
            name="Computer Engineering", campus=self.campus
        )
        self.admin = User.objects.create_user(
            email="cluster-admin@example.com", password="secret123", is_staff=True
        )
        self.uploader = User.objects.create_user(
            email="cluster-uploader@example.com", password="secret123"
        )

    def _publish(self, cluster_value):
        job = IngestionJob.objects.create(
            file=SimpleUploadedFile("r.pdf", b"%PDF-1.4", content_type="application/pdf"),
            original_filename="r.pdf",
            uploaded_by=self.uploader,
            status=IngestionJob.Status.EXTRACTED,
            extracted_payload={
                "project_fields": {
                    "title": "Cluster Test",
                    "abstract": "Abstract.",
                    "department_name": self.department.name,
                    "campus_name": self.campus.name,
                    "cluster": cluster_value,
                },
                "people_and_roles": [{"full_name": "Alice Example", "role": "Author"}],
                "project_sections": [],
            },
        )
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.post(reverse("ingestion:job-publish", args=[job.id]))
        self.assertEqual(response.status_code, 200, response.data)
        job.refresh_from_db()
        return job.published_project

    def test_valid_cluster_is_stored(self):
        self.assertEqual(self._publish("EDMES").cluster, "EDMES")

    def test_lowercase_cluster_is_normalised(self):
        self.assertEqual(self._publish("ipcv").cluster, "IPCV")

    def test_arbitrary_cluster_is_rejected_not_stored(self):
        self.assertIsNone(self._publish("NOT_A_CLUSTER").cluster)

    def test_missing_cluster_is_allowed(self):
        self.assertIsNone(self._publish(None).cluster)

    def test_patch_payload_rejects_an_invalid_cluster(self):
        job = IngestionJob.objects.create(
            file=SimpleUploadedFile("r2.pdf", b"%PDF-1.4", content_type="application/pdf"),
            original_filename="r2.pdf",
            uploaded_by=self.uploader,
            status=IngestionJob.Status.EXTRACTED,
            extracted_payload={"project_fields": {"title": "x"}},
        )
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.patch(
            reverse("ingestion:job-detail", args=[job.id]),
            {"project_fields": {"cluster": "BOGUS"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)


class CanonicalDepartmentTests(TestCase):
    """Free-text department names off a cover page map onto the six real
    departments, and anything ambiguous returns None so a reviewer is asked
    rather than a project being filed under a guess."""

    def test_exact_canonical_names_match_themselves(self):
        from organization.departments import CANONICAL_DEPARTMENTS, canonical_department

        for name in CANONICAL_DEPARTMENTS:
            self.assertEqual(canonical_department(name), name)

    def test_common_cover_page_variants(self):
        from organization.departments import canonical_department

        cases = {
            "DOECE": "Department of Electronics and Computer Engineering",
            "Dept. of Electronics & Computer Engg.": "Department of Electronics and Computer Engineering",
            "DEPARTMENT OF COMPUTER ENGINEERING": "Department of Electronics and Computer Engineering",
            "Department of Electrical Engineering": "Department of Electrical Engineering",
            "department of civil engg": "Department of Civil Engineering",
            "Department of Mechanical Engineering": "Department of Mechanical and Aerospace Engineering",
            "Aerospace Engineering": "Department of Mechanical and Aerospace Engineering",
            "Applied Sciences": "Department of Applied Sciences and Chemical Engineering",
            "Department of Architecture": "Department of Architecture",
        }
        for raw, expected in cases.items():
            self.assertEqual(canonical_department(raw), expected, raw)

    def test_electrical_and_electronics_are_not_confused(self):
        from organization.departments import canonical_department

        self.assertEqual(
            canonical_department("Electrical Engineering"),
            "Department of Electrical Engineering",
        )
        self.assertEqual(
            canonical_department("Electronics Engineering"),
            "Department of Electronics and Computer Engineering",
        )

    def test_unrecognisable_names_return_none(self):
        from organization.departments import canonical_department

        for raw in ["", None, "Tribhuvan University", "Pulchowk Campus", "12345"]:
            self.assertIsNone(canonical_department(raw))


class PublishDepartmentResolutionTests(TestCase):
    """The department seeded by migration must actually be attached to a
    published project. Previously the lookup fell through to
    `Department.objects.first()` -- and with an empty table that was None,
    so every project published with department = NULL."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="dept-admin@example.com", password="secret123", is_staff=True
        )
        self.uploader = User.objects.create_user(
            email="dept-uploader@example.com", password="secret123"
        )

    def _publish(self, department_name):
        job = IngestionJob.objects.create(
            file=SimpleUploadedFile("r.pdf", b"%PDF-1.4", content_type="application/pdf"),
            original_filename="r.pdf",
            uploaded_by=self.uploader,
            status=IngestionJob.Status.EXTRACTED,
            extracted_payload={
                "project_fields": {
                    "title": "Department Test",
                    "abstract": "Abstract.",
                    "department_name": department_name,
                    "campus_name": "Pulchowk Campus",
                },
                "people_and_roles": [{"full_name": "Alice Example", "role": "Author"}],
                "project_sections": [],
            },
        )
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.post(reverse("ingestion:job-publish", args=[job.id]))
        self.assertEqual(response.status_code, 200, response.data)
        job.refresh_from_db()
        return job.published_project

    def test_seeded_departments_exist(self):
        self.assertEqual(Department.objects.count(), 6)

    def test_exact_department_name_is_attached(self):
        project = self._publish("Department of Civil Engineering")
        self.assertIsNotNone(project.department)
        self.assertEqual(project.department.name, "Department of Civil Engineering")

    def test_cover_page_abbreviation_resolves(self):
        project = self._publish("DOECE")
        self.assertEqual(
            project.department.name,
            "Department of Electronics and Computer Engineering",
        )

    def test_unmatched_name_leaves_department_unset_rather_than_guessing(self):
        project = self._publish("Some Unrelated Institute")
        self.assertIsNone(project.department)

    def test_department_is_returned_by_the_api(self):
        project = self._publish("Department of Architecture")
        response = APIClient().get(
            reverse("repository:project-detail", args=[project.id])
        )
        self.assertEqual(response.data["data"]["department"], "Department of Architecture")

    def test_facets_expose_the_department_vocabulary(self):
        data = APIClient().get(reverse("repository:project-facets")).data["data"]
        self.assertEqual(len(data["department_choices"]), 6)
        self.assertIn(
            "Department of Electronics and Computer Engineering",
            data["department_choices"],
        )


class SupervisorPersistedAndDisplayedTests(TestCase):
    """A supervisor present in the extracted payload must reach the
    project, the API and therefore the UI."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="sup-admin@example.com", password="secret123", is_staff=True
        )
        self.uploader = User.objects.create_user(
            email="sup-uploader@example.com", password="secret123"
        )

    def _publish(self, payload_extra):
        base = {
            "project_fields": {
                "title": "Supervisor Test",
                "abstract": "Abstract.",
                "department_name": "Department of Civil Engineering",
                "campus_name": "Pulchowk Campus",
            },
            "people_and_roles": [{"full_name": "Alice Example", "role": "Author"}],
            "project_sections": [],
        }
        base["project_fields"].update(payload_extra.get("project_fields", {}))
        base["people_and_roles"] = payload_extra.get(
            "people_and_roles", base["people_and_roles"]
        )
        job = IngestionJob.objects.create(
            file=SimpleUploadedFile("r.pdf", b"%PDF-1.4", content_type="application/pdf"),
            original_filename="r.pdf",
            uploaded_by=self.uploader,
            status=IngestionJob.Status.EXTRACTED,
            extracted_payload=base,
        )
        client = APIClient()
        client.force_authenticate(user=self.admin)
        response = client.post(reverse("ingestion:job-publish", args=[job.id]))
        self.assertEqual(response.status_code, 200, response.data)
        job.refresh_from_db()
        return job.published_project

    def _api(self, project):
        response = APIClient().get(
            reverse("repository:project-detail", args=[project.id])
        )
        self.assertEqual(response.status_code, 200)
        return response.data["data"]

    def test_supervisor_in_people_and_roles_reaches_the_api(self):
        project = self._publish({
            "people_and_roles": [
                {"full_name": "Alice Example", "role": "Author"},
                {"full_name": "Bikal Adhikari", "role": "Supervisor",
                 "designation": "Associate Professor"},
            ]
        })
        data = self._api(project)
        self.assertTrue(any("Bikal Adhikari" in s for s in data["supervisors"]))
        self.assertIn("Bikal Adhikari", data["supervisor"])

    def test_supervisor_only_in_project_fields_is_not_lost(self):
        # Some extracted payloads record the supervisor here and nowhere
        # else; it must still become a ProjectPerson.
        project = self._publish({
            "project_fields": {
                "supervisors": [
                    {"full_name": "Rita Shakya", "designation": "Professor"}
                ]
            }
        })
        self.assertTrue(
            ProjectPerson.objects.filter(
                project=project, role="Supervisor", person__full_name="Rita Shakya"
            ).exists()
        )
        self.assertTrue(any("Rita Shakya" in s for s in self._api(project)["supervisors"]))

    def test_no_supervisor_yields_an_empty_list_not_a_placeholder(self):
        data = self._api(self._publish({}))
        self.assertEqual(data["supervisors"], [])
        self.assertEqual(data["supervisor"], "")

    def test_examiner_is_not_reported_as_a_supervisor(self):
        project = self._publish({
            "people_and_roles": [
                {"full_name": "Alice Example", "role": "Author"},
                {"full_name": "Dibakar Pant", "role": "Internal Examiner"},
            ]
        })
        self.assertEqual(self._api(project)["supervisors"], [])


class FilterAwareFacetTests(TestCase):
    """
    A facet count must equal what selecting that option returns.

    Counts used to be computed unconditionally, so with one filter already
    active another facet could still advertise its whole-catalogue count
    and then yield nothing when clicked -- which read as "the first click
    shows no results".
    """

    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.dept_a = Department.objects.create(name="Dept A", campus=campus)
        self.dept_b = Department.objects.create(name="Dept B", campus=campus)
        self.supervisor = Faculty.objects.create(full_name="Sita Rai", department=self.dept_a)

        # UG projects are batch 078; the Masters one is batch 077, so
        # "Masters + 078" is an empty combination.
        self._project("UG one", self.dept_a, "UG", "078", "AIML", self.supervisor)
        self._project("UG two", self.dept_a, "UG", "078", "AIML", None)
        self._project("Masters one", self.dept_b, "Masters", "077", "NTS", None)

    def _project(self, title, dept, level, batch, cluster, supervisor):
        project = Project.objects.create(
            title=title, abstract="a", project_type="Major", academic_level=level,
            batch=batch, status="Published", department=dept, cluster=cluster,
        )
        if supervisor:
            ProjectPerson.objects.create(
                project=project, person=supervisor, role="Supervisor", display_order=1
            )
        return project

    def _facets(self, **params):
        response = APIClient().get(reverse("repository:project-facets"), params)
        self.assertEqual(response.status_code, 200)
        return response.data["data"]

    def _results(self, **params):
        response = APIClient().get(reverse("repository:project-list"), params)
        self.assertEqual(response.status_code, 200)
        return response.data["data"]

    def test_unfiltered_counts_match_unfiltered_results(self):
        facets = self._facets()
        for option in facets["batches"]:
            self.assertEqual(
                len(self._results(batch=option["name"])), option["count"], option["name"]
            )

    def test_counts_narrow_when_another_filter_is_active(self):
        # With Masters selected, batch 078 holds nothing -- and must say so
        # rather than still advertising its unfiltered count of 2.
        facets = self._facets(academic_level="Masters")
        batches = {b["name"]: b["count"] for b in facets["batches"]}

        self.assertNotIn("078", batches)
        self.assertEqual(batches.get("077"), 1)

    def test_every_advertised_option_returns_exactly_its_count(self):
        """The property that was broken: clicking any offered option, with
        other filters already applied, returns precisely its badge."""
        for active in ({}, {"academic_level": "UG"}, {"cluster": "AIML"},
                       {"department": "Dept A"}, {"batch": "078"}):
            facets = self._facets(**active)
            for dimension, key in (
                ("batches", "batch"),
                ("academic_levels", "academic_level"),
                ("departments", "department"),
                ("clusters", "cluster"),
                ("supervisors", "supervisor"),
            ):
                for option in facets[dimension]:
                    combined = dict(active)
                    combined[key] = option["name"]
                    self.assertEqual(
                        len(self._results(**combined)),
                        option["count"],
                        f"active={active} {key}={option['name']!r}",
                    )

    def test_total_reflects_the_active_filters(self):
        self.assertEqual(self._facets()["total"], 3)
        self.assertEqual(self._facets(academic_level="UG")["total"], 2)
        self.assertEqual(self._facets(academic_level="Masters")["total"], 1)

    def test_search_is_honoured_by_the_counts(self):
        facets = self._facets(q="Masters one")
        self.assertEqual(facets["total"], 1)
        self.assertEqual([b["name"] for b in facets["batches"]], ["077"])

    def test_fixed_vocabularies_are_still_returned(self):
        facets = self._facets(academic_level="UG")
        self.assertEqual(len(facets["cluster_choices"]), 7)
        self.assertEqual(len(facets["department_choices"]), 6)


class ReportAccessRequestTests(TestCase):
    """
    The in-app replacement for emailing the authors: a reader asks, every
    reviewer is notified, any one of them decides, and an approval
    immediately unlocks the report for that reader.
    """

    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.department = Department.objects.create(name="Dept X", campus=campus)

        self.project = Project.objects.create(
            title="Restricted Report Project",
            abstract="Public abstract.",
            project_type="Major",
            academic_level="UG",
            batch="078",
            status="Published",
            department=self.department,
        )
        ProjectAsset.objects.create(
            project=self.project,
            asset_type="Report",
            file=SimpleUploadedFile("report.pdf", b"%PDF-1.4", content_type="application/pdf"),
            mime_type="application/pdf",
            file_size=9,
        )

        self.student = User.objects.create_user(email="student@example.com", password="secret123")
        self.other_student = User.objects.create_user(email="other@example.com", password="secret123")
        self.admin_a = User.objects.create_user(
            email="admin-a@example.com", password="secret123", is_staff=True
        )
        self.admin_b = User.objects.create_user(
            email="admin-b@example.com", password="secret123", is_staff=True
        )

    def _client(self, user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user=user)
        return client

    def _request_access(self, user, reason="Needed for my literature review."):
        return self._client(user).post(
            reverse("repository:access-request-create", args=[self.project.id]),
            {"reason": reason},
        )

    def _detail(self, user=None):
        response = self._client(user).get(
            reverse("repository:project-detail", args=[self.project.id])
        )
        self.assertEqual(response.status_code, 200)
        return response.data["data"]

    # ---- requesting ---------------------------------------------------

    def test_request_requires_sign_in(self):
        response = APIClient().post(
            reverse("repository:access-request-create", args=[self.project.id])
        )
        self.assertIn(response.status_code, (401, 403))

    def test_request_notifies_every_admin(self):
        self.assertEqual(self._request_access(self.student).status_code, 201)

        for admin in (self.admin_a, self.admin_b):
            self.assertTrue(
                Notification.objects.filter(
                    recipient=admin,
                    notification_type=Notification.NotificationType.ACCESS_REQUESTED,
                    project=self.project,
                ).exists(),
                f"{admin.email} was not notified",
            )
        # The requester is not notified of their own request.
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.student,
                notification_type=Notification.NotificationType.ACCESS_REQUESTED,
            ).exists()
        )

    def test_duplicate_request_does_not_stack_up(self):
        self.assertEqual(self._request_access(self.student).status_code, 201)
        second = self._request_access(self.student)

        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            ProjectAccessRequest.objects.filter(
                project=self.project, requester=self.student
            ).count(),
            1,
        )

    # ---- deciding -----------------------------------------------------

    def test_only_a_reviewer_can_decide(self):
        self._request_access(self.student)
        access_request = ProjectAccessRequest.objects.get()

        response = self._client(self.other_student).post(
            reverse("repository:access-request-decision", args=[access_request.id, "approve"])
        )
        self.assertEqual(response.status_code, 403)
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, ProjectAccessRequest.Status.PENDING)

    def test_any_admin_can_approve_and_the_student_is_notified(self):
        self._request_access(self.student)
        access_request = ProjectAccessRequest.objects.get()

        response = self._client(self.admin_b).post(
            reverse("repository:access-request-decision", args=[access_request.id, "approve"])
        )
        self.assertEqual(response.status_code, 200, response.data)

        access_request.refresh_from_db()
        self.assertEqual(access_request.status, ProjectAccessRequest.Status.APPROVED)
        self.assertEqual(access_request.decided_by, self.admin_b)
        self.assertIsNotNone(access_request.decided_at)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student,
                notification_type=Notification.NotificationType.ACCESS_APPROVED,
                project=self.project,
            ).exists()
        )

    def test_decline_notifies_the_student_and_does_not_grant(self):
        self._request_access(self.student)
        access_request = ProjectAccessRequest.objects.get()

        self._client(self.admin_a).post(
            reverse("repository:access-request-decision", args=[access_request.id, "decline"])
        )

        access_request.refresh_from_db()
        self.assertEqual(access_request.status, ProjectAccessRequest.Status.DECLINED)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.student,
                notification_type=Notification.NotificationType.ACCESS_DECLINED,
            ).exists()
        )
        self.assertIsNone(self._detail(self.student)["pdfUrl"])

    def test_a_request_cannot_be_decided_twice(self):
        self._request_access(self.student)
        access_request = ProjectAccessRequest.objects.get()
        url = reverse("repository:access-request-decision", args=[access_request.id, "approve"])

        self.assertEqual(self._client(self.admin_a).post(url).status_code, 200)
        self.assertEqual(self._client(self.admin_b).post(url).status_code, 400)

    # ---- what approval actually unlocks --------------------------------

    def test_report_is_hidden_until_approved_then_visible(self):
        self.assertIsNone(self._detail(self.student)["pdfUrl"])
        self.assertEqual(self._detail(self.student)["accessStatus"], "none")

        self._request_access(self.student)
        self.assertEqual(self._detail(self.student)["accessStatus"], "pending")
        self.assertIsNone(self._detail(self.student)["pdfUrl"])

        access_request = ProjectAccessRequest.objects.get()
        self._client(self.admin_a).post(
            reverse("repository:access-request-decision", args=[access_request.id, "approve"])
        )

        granted = self._detail(self.student)
        self.assertEqual(granted["accessStatus"], "granted")
        self.assertIsNotNone(granted["pdfUrl"])

    def test_approval_grants_only_the_requester(self):
        self._request_access(self.student)
        self._client(self.admin_a).post(
            reverse(
                "repository:access-request-decision",
                args=[ProjectAccessRequest.objects.get().id, "approve"],
            )
        )

        self.assertIsNone(self._detail(self.other_student)["pdfUrl"])
        self.assertIsNone(self._detail()["pdfUrl"])

    def test_approval_does_not_expose_the_report_body(self):
        """Access to the PDF is not access to the extracted sections."""
        ProjectSection.objects.create(
            project=self.project, heading="Introduction", heading_level=1,
            display_order=1, content="CONFIDENTIAL BODY",
        )
        self._request_access(self.student)
        self._client(self.admin_a).post(
            reverse(
                "repository:access-request-decision",
                args=[ProjectAccessRequest.objects.get().id, "approve"],
            )
        )

        data = self._detail(self.student)
        self.assertIsNotNone(data["pdfUrl"])
        self.assertEqual(data["sections"], [])
        self.assertTrue(data["sections_restricted"])

    # ---- queues --------------------------------------------------------

    def test_reviewer_queue_lists_requests_and_students_cannot_read_it(self):
        self._request_access(self.student)

        queue = self._client(self.admin_a).get(reverse("repository:access-request-queue"))
        self.assertEqual(queue.status_code, 200)
        self.assertEqual(len(queue.data["data"]), 1)
        self.assertEqual(queue.data["data"][0]["requester_email"], "student@example.com")

        self.assertEqual(
            self._client(self.other_student)
            .get(reverse("repository:access-request-queue"))
            .status_code,
            403,
        )

    def test_my_requests_are_scoped_to_the_signed_in_user(self):
        self._request_access(self.student)

        mine = self._client(self.student).get(reverse("repository:access-request-mine"))
        self.assertEqual(len(mine.data["data"]), 1)

        theirs = self._client(self.other_student).get(reverse("repository:access-request-mine"))
        self.assertEqual(theirs.data["data"], [])


class ProjectManageTests(TestCase):
    """Reviewer-only edit and delete of a published catalogue record."""

    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.department = Department.objects.create(
            name="Department of Civil Engineering", campus=campus
        )
        self.project = Project.objects.create(
            title="Editable Project",
            abstract="Before.",
            project_type="Major",
            academic_level="UG",
            batch="078",
            status="Published",
            department=self.department,
        )
        self.admin = User.objects.create_user(
            email="mgr@example.com", password="secret123", is_staff=True
        )
        self.student = User.objects.create_user(email="nope@example.com", password="secret123")

    def _client(self, user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user=user)
        return client

    def _url(self):
        return reverse("repository:project-manage", args=[self.project.id])

    def test_students_cannot_edit_or_delete(self):
        self.assertEqual(
            self._client(self.student).patch(self._url(), {"title": "Hacked"}, format="json").status_code,
            403,
        )
        self.assertEqual(self._client(self.student).delete(self._url()).status_code, 403)
        self.assertEqual(APIClient().delete(self._url()).status_code, 401)
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Editable Project")

    def test_admin_can_edit_catalogue_metadata(self):
        response = self._client(self.admin).patch(
            self._url(),
            {
                "title": "Edited Project",
                "abstract": "After.",
                "cluster": "aiml",
                "academic_level": "Masters",
                "keywords": ["robotics", "control"],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)

        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Edited Project")
        self.assertEqual(self.project.abstract, "After.")
        self.assertEqual(self.project.cluster, "AIML")
        self.assertEqual(self.project.academic_level, "Masters")
        self.assertCountEqual(response.data["data"]["keywords"], ["robotics", "control"])

    def test_invalid_values_are_rejected(self):
        for payload in ({"title": "   "}, {"cluster": "NOPE"}, {"academic_level": "Wizard"}):
            response = self._client(self.admin).patch(self._url(), payload, format="json")
            self.assertEqual(response.status_code, 400, payload)
        self.project.refresh_from_db()
        self.assertEqual(self.project.title, "Editable Project")

    def test_department_is_resolved_against_the_real_departments(self):
        response = self._client(self.admin).patch(
            self._url(), {"department_name": "DOECE"}, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.project.refresh_from_db()
        self.assertEqual(
            self.project.department.name,
            "Department of Electronics and Computer Engineering",
        )

    def test_admin_can_delete_a_project(self):
        project_id = self.project.id
        response = self._client(self.admin).delete(self._url())

        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(Project.objects.filter(id=project_id).exists())

    def test_deleting_a_project_keeps_its_ingestion_job(self):
        """The deposit and its PDF survive, so a record removed by mistake
        can be published again from the source."""
        uploader = User.objects.create_user(email="dep@example.com", password="secret123")
        job = IngestionJob.objects.create(
            file=SimpleUploadedFile("r.pdf", b"%PDF-1.4", content_type="application/pdf"),
            original_filename="r.pdf",
            uploaded_by=uploader,
            status=IngestionJob.Status.VERIFIED,
            published_project=self.project,
        )

        self._client(self.admin).delete(self._url())

        job.refresh_from_db()
        self.assertIsNone(job.published_project)
        self.assertTrue(job.file)
