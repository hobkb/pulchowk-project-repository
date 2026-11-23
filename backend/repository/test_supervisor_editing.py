

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import Faculty, Student, User
from organization.models import Campus, Department
from repository.models import Project, ProjectPerson


class SupervisorEditingTests(APITestCase):
    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.dept = Department.objects.create(name="Dept S", campus=campus)
        self.project = Project.objects.create(
            title="A Project", status="Published", department=self.dept,
            batch="078", academic_level="UG",
        )
        self.author = Student.objects.create(
            full_name="Asha Rai", roll_number="080BCT500", academic_level="UG"
        )
        ProjectPerson.objects.create(
            project=self.project, person=self.author, role="Author", display_order=1
        )
        self.admin = User.objects.create_user(
            email="sup-admin@pcampus.edu.np", password="x",
            is_staff=True, is_superuser=True, role="admin",
        )
        self.client.force_authenticate(user=self.admin)

    def patch(self, payload):
        return self.client.patch(
            reverse("repository:project-manage", args=[self.project.id]),
            payload, format="json",
        )

    def supervisors(self):
        return list(
            ProjectPerson.objects
            .filter(project=self.project, role__in=["Supervisor", "Co-Supervisor"])
            .values_list("person__full_name", flat=True)
        )

    # ------------------------------------------------------------------

    def test_a_supervisor_can_be_added_after_publication(self):
        response = self.patch({"supervisors": [
            {"full_name": "Ram Krishna Maharjan", "title": "Dr.", "designation": "Professor"},
        ]})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(self.supervisors(), ["Ram Krishna Maharjan"])

        faculty = Faculty.objects.get(full_name="Ram Krishna Maharjan")
        self.assertEqual(faculty.title, "Dr.")
        self.assertEqual(faculty.designation, "Professor")

    def test_it_reuses_an_existing_faculty_record(self):
        """The whole point: no second record for a known supervisor."""
        existing = Faculty.objects.create(
            full_name="Ram Krishna Maharjan", title="Dr.", designation="Professor"
        )
        self.patch({"supervisors": [{"full_name": "ram krishna maharjan"}]})

        self.assertEqual(
            Faculty.objects.filter(full_name__iexact="Ram Krishna Maharjan").count(), 1
        )
        link = ProjectPerson.objects.get(project=self.project, role="Supervisor")
        self.assertEqual(link.person_id, existing.id)

    def test_a_blank_field_never_clears_what_is_on_record(self):
        Faculty.objects.create(
            full_name="Ram Krishna Maharjan", title="Dr.", designation="Professor"
        )
        self.patch({"supervisors": [
            {"full_name": "Ram Krishna Maharjan", "title": "", "designation": ""},
        ]})
        faculty = Faculty.objects.get(full_name="Ram Krishna Maharjan")
        self.assertEqual(faculty.title, "Dr.")
        self.assertEqual(faculty.designation, "Professor")

    def test_supervisors_are_replaced_wholesale(self):
        self.patch({"supervisors": [{"full_name": "First Supervisor"}]})
        self.patch({"supervisors": [{"full_name": "Second Supervisor"}]})
        self.assertEqual(self.supervisors(), ["Second Supervisor"])

    def test_authors_are_left_alone(self):
        self.patch({"supervisors": [{"full_name": "Ram Krishna Maharjan"}]})
        self.assertTrue(
            ProjectPerson.objects.filter(
                project=self.project, person=self.author, role="Author"
            ).exists()
        )

    def test_an_empty_list_removes_every_supervisor(self):
        self.patch({"supervisors": [{"full_name": "Ram Krishna Maharjan"}]})
        self.patch({"supervisors": []})
        self.assertEqual(self.supervisors(), [])

    def test_omitting_the_field_leaves_supervisors_untouched(self):
        self.patch({"supervisors": [{"full_name": "Ram Krishna Maharjan"}]})
        self.patch({"title": "A Renamed Project"})
        self.assertEqual(self.supervisors(), ["Ram Krishna Maharjan"])

    def test_the_same_person_twice_produces_one_link(self):
        self.patch({"supervisors": [
            {"full_name": "Ram Krishna Maharjan"},
            {"full_name": "Ram Krishna Maharjan"},
        ]})
        self.assertEqual(len(self.supervisors()), 1)

    def test_a_name_held_by_a_student_is_reported_not_crashed(self):
        self.patch({"supervisors": [{"full_name": "Asha Rai"}]})
        response = self.patch({"supervisors": [{"full_name": "Asha Rai"}]})
        self.assertEqual(response.status_code, 400, response.data)

    def test_an_ordinary_reader_cannot_edit_supervisors(self):
        reader = User.objects.create_user(email="sup-reader@pcampus.edu.np", password="x")
        self.client.force_authenticate(user=reader)
        response = self.patch({"supervisors": [{"full_name": "Ram Krishna Maharjan"}]})
        self.assertEqual(response.status_code, 403)

    def test_the_response_carries_the_editable_records_back(self):
        response = self.patch({"supervisors": [
            {"full_name": "Ram Krishna Maharjan", "title": "Dr.", "designation": "Professor"},
        ]})
        records = response.data["data"]["supervisorRecords"]
        self.assertEqual(records[0]["full_name"], "Ram Krishna Maharjan")
        self.assertEqual(records[0]["title"], "Dr.")
        self.assertEqual(records[0]["designation"], "Professor")
