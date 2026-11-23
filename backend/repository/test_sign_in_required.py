from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from organization.models import Campus, Department
from repository.models import Project


class SignInRequiredTests(TestCase):
    """Nothing in the catalogue is readable without a campus sign-in."""

    @classmethod
    def setUpTestData(cls):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        dept = Department.objects.create(name="Electronics Engineering", campus=campus)
        cls.project = Project.objects.create(
            title="Signed-in only",
            abstract="Readable after sign-in.",
            project_type="Major",
            academic_level="UG",
            department=dept,
            status="Published",
        )

    def test_every_catalogue_and_directory_endpoint_refuses_anonymous_readers(self):
        urls = [
            reverse("repository:project-list"),
            reverse("repository:project-facets"),
            reverse("repository:project-choices"),
            reverse("repository:project-detail", args=[self.project.id]),
            reverse("repository:project-similar", args=[self.project.id]),
            "/api/organization/campuses/",
            "/api/organization/departments/",
            "/api/organization/research-groups/",
            "/api/accounts/faculty/",
            "/api/accounts/students/",
        ]
        client = APIClient()
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(client.get(url).status_code, 401)

    def test_sign_in_itself_stays_reachable(self):
        response = APIClient().post("/api/accounts/google/login/", {}, format="json")
        self.assertNotIn(response.status_code, (401, 403))
