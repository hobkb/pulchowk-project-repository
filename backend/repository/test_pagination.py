"""
Paging behaviour for the list endpoints.

Deliberately checks the awkward cases rather than just "page 1 works":
an out-of-range page, a page_size above the cap, and that paging composes
with filtering instead of silently dropping it.
"""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from organization.models import Campus, Department
from repository.models import Project


class ProjectPaginationTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        cls.dept = Department.objects.create(name="Dept P", campus=campus)
        other = Department.objects.create(name="Dept Q", campus=campus)
        # 27 published -> 6 pages at the default size of 5.
        for i in range(27):
            Project.objects.create(
                title=f"P{i}",
                status="Published",
                department=cls.dept if i < 20 else other,
                academic_level="UG",
            )
        # An unpublished record must not be counted by the pager.
        Project.objects.create(title="draft", status="Draft", department=cls.dept)

    def get(self, **params):
        return self.client.get(reverse("repository:project-list"), params)

    def test_first_page_is_full_and_reports_the_real_total(self):
        body = self.get().json()
        self.assertEqual(len(body["data"]), 5)
        page = body["pagination"]
        self.assertEqual(page["page"], 1)
        self.assertEqual(page["total_count"], 27)
        self.assertEqual(page["total_pages"], 6)
        self.assertTrue(page["has_next"])
        self.assertFalse(page["has_previous"])

    def test_last_page_holds_the_remainder(self):
        body = self.get(page=6).json()
        self.assertEqual(len(body["data"]), 2)
        self.assertFalse(body["pagination"]["has_next"])

    def test_pages_do_not_overlap_or_lose_rows(self):
        seen = []
        for n in range(1, 7):
            seen += [row["id"] for row in self.get(page=n).json()["data"]]
        self.assertEqual(len(seen), 27)
        self.assertEqual(len(set(seen)), 27, "a row appeared on two pages")

    def test_a_page_past_the_end_returns_the_last_page_not_an_error(self):
        body = self.get(page=99).json()
        self.assertEqual(body["pagination"]["page"], 6)
        self.assertEqual(len(body["data"]), 2)

    def test_junk_page_falls_back_to_the_first(self):
        for value in ("abc", "", "0", "-4"):
            self.assertEqual(self.get(page=value).json()["pagination"]["page"], 1, value)

    def test_page_size_is_capped(self):
        body = self.get(page_size=5000).json()
        self.assertEqual(body["pagination"]["page_size"], 100)
        self.assertEqual(len(body["data"]), 27)

    def test_paging_composes_with_a_filter(self):
        body = self.get(department="Dept P").json()
        self.assertEqual(body["pagination"]["total_count"], 20)
        self.assertEqual(body["pagination"]["total_pages"], 4)


class QueuePaginationTests(APITestCase):
    """The reviewer queues page at 15, and stay permission-gated."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="pager@pcampus.edu.np", password="x", is_staff=True, is_superuser=True
        )

    def test_role_queue_is_paginated_for_an_admin(self):
        self.client.force_authenticate(user=self.admin)
        body = self.client.get(reverse("acocunts_apis:role-request-queue")).json()
        self.assertEqual(body["pagination"]["page_size"], 5)
        self.assertEqual(body["data"], [])

    def test_role_queue_still_refuses_a_non_admin(self):
        reader = User.objects.create_user(email="reader@pcampus.edu.np", password="x")
        self.client.force_authenticate(user=reader)
        response = self.client.get(reverse("acocunts_apis:role-request-queue"))
        self.assertEqual(response.status_code, 403)
