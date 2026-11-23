

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Faculty
from ingestion.pipeline.utils.text_cleaners import (
    split_person_title,
    split_title_and_designation,
)
from organization.models import Campus, Department
from repository.models import Project, ProjectPerson
from repository.testing import reader_client


class SplitTitleAndDesignationTests(SimpleTestCase):
    def test_an_honorific_and_a_rank_are_separated(self):
        self.assertEqual(split_title_and_designation("Prof. Dr."), ("Dr.", "Prof."))

    def test_a_compound_rank_is_not_split_across_the_two_fields(self):
        self.assertEqual(split_title_and_designation("Asst. Prof."), ("", "Asst. Prof."))
        self.assertEqual(
            split_title_and_designation("Assistant Professor"), ("", "Assistant Professor")
        )

    def test_a_bare_honorific_leaves_no_rank(self):
        self.assertEqual(split_title_and_designation("Dr."), ("Dr.", ""))
        self.assertEqual(split_title_and_designation("Er."), ("Er.", ""))

    def test_nothing_in_gives_nothing_out(self):
        self.assertEqual(split_title_and_designation(""), ("", ""))
        self.assertEqual(split_title_and_designation(None), ("", ""))

    def test_it_composes_with_the_name_splitter(self):
        name, prefix = split_person_title("Prof. Dr. Manoj Shrestha")
        self.assertEqual(name, "Manoj Shrestha")
        self.assertEqual(split_title_and_designation(prefix), ("Dr.", "Prof."))

    def test_the_engineer_honorific_is_split_from_the_name(self):
        self.assertEqual(split_person_title("Er. Ram Sharma"), ("Ram Sharma", "Er."))
        name, prefix = split_person_title("Asst. Prof. Er. Ram Sharma")
        self.assertEqual(name, "Ram Sharma")
        self.assertEqual(split_title_and_designation(prefix), ("Er.", "Asst. Prof."))

    def test_a_name_that_merely_starts_with_er_is_left_alone(self):
        self.assertEqual(split_person_title("Erina Shrestha"), ("Erina Shrestha", ""))


class SupervisorDisplayTests(TestCase):
    """What the catalogue and the facet list actually render."""

    @classmethod
    def setUpTestData(cls):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        cls.dept = Department.objects.create(name="Electronics Engineering", campus=campus)

        cls.doctor = Faculty.objects.create(
            full_name="Rajiv Bhandari",
            department=cls.dept,
            title="Dr.",
            designation="Assistant Professor",
        )
        cls.plain = Faculty.objects.create(
            full_name="Santosh Giri",
            department=cls.dept,
            designation="Assistant Professor",
        )

        cls.with_doctor = cls._project("Doctor supervised", cls.doctor)
        cls._project("Plainly supervised", cls.plain)

    @classmethod
    def _project(cls, title, supervisor):
        project = Project.objects.create(
            title=title, status="Published", department=cls.dept,
            batch="078", academic_level="UG",
        )
        ProjectPerson.objects.create(
            project=project, person=supervisor, role="Supervisor", display_order=1
        )
        return project

    def test_the_project_page_shows_the_honorific_with_the_rank(self):
        response = reader_client().get(
            reverse("repository:project-detail", args=[self.with_doctor.id])
        )
        supervisors = response.data["data"]["supervisors"]
        self.assertEqual(len(supervisors), 1)
        self.assertIn("Dr.", supervisors[0])
        self.assertIn("Rajiv Bhandari", supervisors[0])
        self.assertIn("Asst. Prof.", supervisors[0])

    def test_a_supervisor_without_an_honorific_reads_cleanly(self):
        response = reader_client().get(reverse("repository:project-list"))
        rows = {r["title"]: r for r in response.data["data"]}
        plain = rows["Plainly supervised"]["supervisors"][0]
        self.assertEqual(plain, "Asst. Prof. Santosh Giri")
        self.assertNotIn("  ", plain)

    def test_the_search_facet_carries_the_honorific_separately(self):
        data = reader_client().get(reverse("repository:project-facets")).data["data"]
        by_name = {row["name"]: row for row in data["supervisors"]}

        self.assertEqual(by_name["Rajiv Bhandari"]["title"], "Dr.")
        self.assertEqual(by_name["Rajiv Bhandari"]["designation"], "Assistant Professor")
        # The filter still matches on the bare name.
        self.assertEqual(by_name["Santosh Giri"]["title"], "")
