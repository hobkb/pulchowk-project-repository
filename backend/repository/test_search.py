"""
Free-text search over the catalogue.

The search box is ordinary substring matching over stored fields -- there
is no ranking model behind it. These cover what a reader actually types:
a supervisor's surname, a rank, a cluster code, and combinations that span
more than one field.
"""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Faculty, Student
from organization.models import Campus, Department
from repository.models import Project, ProjectPerson


class SearchTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        cls.dept = Department.objects.create(name="Electronics Engineering", campus=campus)

        cls.supervisor = Faculty.objects.create(
            full_name="Bikal Adhikari",
            department=cls.dept,
            title="Dr.",
            designation="Associate Professor",
        )
        cls.other_supervisor = Faculty.objects.create(
            full_name="Rita Shakya",
            department=cls.dept,
            designation="Assistant Professor",
        )
        cls.author = Student.objects.create(
            full_name="Nischal Karki", roll_number="078BEL099", academic_level="UG"
        )

        cls.vision = cls._project("Vision system for traffic", "AIML", cls.supervisor)
        cls.mesh = cls._project("Mesh routing protocol", "NTS", cls.other_supervisor)

        # The author is on the first project only, so a name search must not
        # be satisfied by a person attached to a different record.
        ProjectPerson.objects.create(
            project=cls.vision, person=cls.author, role="Author", display_order=2
        )

    @classmethod
    def _project(cls, title, cluster, supervisor):
        project = Project.objects.create(
            title=title,
            abstract=f"An abstract for {title.lower()}.",
            status="Published",
            department=cls.dept,
            cluster=cluster,
            batch="078",
            academic_level="UG",
        )
        ProjectPerson.objects.create(
            project=project, person=supervisor, role="Supervisor", display_order=1
        )
        return project

    def search(self, **params):
        response = self.client.get(reverse("repository:project-list"), params)
        self.assertEqual(response.status_code, 200, response.data)
        return sorted(row["title"] for row in response.data["data"])

    # ------------------------------------------------------------ by person

    def test_a_supervisors_surname_finds_their_projects(self):
        self.assertEqual(self.search(q="adhikari"), ["Vision system for traffic"])

    def test_a_partial_name_matches_as_a_substring(self):
        self.assertEqual(self.search(q="adhik"), ["Vision system for traffic"])

    def test_an_authors_name_still_matches(self):
        self.assertEqual(self.search(q="nischal"), ["Vision system for traffic"])

    # -------------------------------------------------------------- by rank

    def test_searching_a_designation_finds_that_supervisors_projects(self):
        self.assertEqual(self.search(q="associate professor"),
                         ["Vision system for traffic"])
        self.assertEqual(self.search(q="assistant professor"),
                         ["Mesh routing protocol"])

    def test_searching_an_academic_title_works(self):
        self.assertEqual(self.search(q="Dr."), ["Vision system for traffic"])

    # ----------------------------------------------------------- by cluster

    def test_a_cluster_code_can_be_typed_into_the_search_box(self):
        self.assertEqual(self.search(q="AIML"), ["Vision system for traffic"])
        self.assertEqual(self.search(q="nts"), ["Mesh routing protocol"])

    def test_the_cluster_filter_accepts_a_substring(self):
        self.assertEqual(self.search(cluster="aiml"), ["Vision system for traffic"])

    def test_the_supervisor_filter_accepts_a_substring(self):
        self.assertEqual(self.search(supervisor="Adhikari"),
                         ["Vision system for traffic"])
        # A facet click sends the full name; that must still work.
        self.assertEqual(self.search(supervisor="Bikal Adhikari"),
                         ["Vision system for traffic"])

    # -------------------------------------------------------- across fields

    def test_terms_may_be_satisfied_by_different_fields(self):
        """"adhikari traffic" -- one term is a person, the other a title."""
        self.assertEqual(self.search(q="adhikari traffic"),
                         ["Vision system for traffic"])

    def test_every_term_must_match_something(self):
        self.assertEqual(self.search(q="adhikari routing"), [])

    def test_a_term_matching_nothing_returns_nothing(self):
        self.assertEqual(self.search(q="zzzznotpresent"), [])

    def test_results_are_not_duplicated_when_several_fields_match(self):
        """A join across people could otherwise return a project twice."""
        titles = self.search(q="adhikari")
        self.assertEqual(len(titles), len(set(titles)))
