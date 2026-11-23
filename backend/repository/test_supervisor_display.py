"""
The catalogue's rendered supervisor string.

A rank typed into the Title field ("Prof.Dr.") duplicates the abbreviation
already computed from the Designation field, producing "Prof. Prof. Dr.
Name" instead of "Prof. Dr. Name". These prove the fix at the level that
actually matters: the string sent to the frontend.
"""

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Faculty
from organization.models import Campus, Department
from repository.models import Project, ProjectPerson
from repository.serializers import _strip_redundant_rank
from repository.testing import reader_client


class StripRedundantRankTests(SimpleTestCase):
    def test_a_rank_typed_into_title_is_removed_when_it_duplicates_designation(self):
        self.assertEqual(_strip_redundant_rank("Prof.Dr.", "Prof."), "Dr.")
        self.assertEqual(_strip_redundant_rank("Prof. Dr.", "Prof."), "Dr.")
        self.assertEqual(_strip_redundant_rank("PROF. DR.", "Prof."), "DR.")

    def test_a_multi_word_rank_is_also_recognised_regardless_of_spacing(self):
        self.assertEqual(
            _strip_redundant_rank("Asst.Prof.Dr.", "Asst. Prof."), "Dr."
        )
        self.assertEqual(
            _strip_redundant_rank("Assoc. Prof. Dr.", "Assoc. Prof."), "Dr."
        )

    def test_a_title_with_no_rank_in_it_is_left_alone(self):
        self.assertEqual(_strip_redundant_rank("Dr.", "Prof."), "Dr.")
        self.assertEqual(_strip_redundant_rank("Er.", "Prof."), "Er.")

    def test_nothing_is_lost_when_there_is_no_designation_to_be_redundant_with(self):
        self.assertEqual(_strip_redundant_rank("Prof. Dr.", ""), "Prof. Dr.")

    def test_empty_input_is_handled(self):
        self.assertEqual(_strip_redundant_rank("", "Prof."), "")
        self.assertEqual(_strip_redundant_rank("Dr.", ""), "Dr.")


class SupervisorDisplayStringTests(TestCase):
    """The end-to-end shape: what the project API actually returns."""

    @classmethod
    def setUpTestData(cls):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        cls.dept = Department.objects.create(name="Dept D", campus=campus)

    def _project(self, faculty):
        project = Project.objects.create(
            title="Some Project", status="Published", department=self.dept,
            batch="078", academic_level="UG",
        )
        ProjectPerson.objects.create(
            project=project, person=faculty, role="Supervisor", display_order=1
        )
        return project

    def test_the_reported_bug_is_fixed(self):
        """designation=Professor, title="Prof.Dr." must render "Prof. Dr. Name"."""
        faculty = Faculty.objects.create(
            full_name="Rajan Bhandari", department=self.dept,
            title="Prof.Dr.", designation="Professor",
        )
        project = self._project(faculty)

        response = reader_client().get(reverse("repository:project-detail", args=[project.id]))
        supervisor = response.data["data"]["supervisors"][0]

        self.assertEqual(supervisor, "Prof. Dr. Rajan Bhandari")
        self.assertNotIn("Prof. Prof.", supervisor)
        self.assertEqual(supervisor.count("Prof"), 1)

    def test_a_normal_record_is_unaffected(self):
        faculty = Faculty.objects.create(
            full_name="Sita Karki", department=self.dept,
            title="Dr.", designation="Assistant Professor",
        )
        project = self._project(faculty)
        response = reader_client().get(reverse("repository:project-detail", args=[project.id]))
        self.assertEqual(
            response.data["data"]["supervisors"][0], "Asst. Prof. Dr. Sita Karki"
        )
