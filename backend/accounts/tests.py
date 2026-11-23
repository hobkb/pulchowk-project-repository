from django.test import TestCase
from django.urls import reverse

from accounts.models import RoleElevationRequest, User
from notifications.models import Notification


class CurrentUserProfileSerializerTests(TestCase):
    """
    /accounts/me/ exposes the linked Person as a read-only `profile`
    block. Without it a client could only see the person's id, which is
    why the account page previously had nothing real to display.
    """

    def setUp(self):
        from organization.models import Campus, Department

        self.campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.department = Department.objects.create(
            name="Electronics Engineering", campus=self.campus
        )

    def _me(self, user):
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(user=user)
        response = client.get(reverse("acocunts_apis:fetch_user"))
        self.assertEqual(response.status_code, 200)
        return response.data["data"]

    def test_profile_is_none_before_onboarding(self):
        user = User.objects.create_user(email="fresh@example.com", password="secret123")
        data = self._me(user)
        self.assertIsNone(data["profile"])
        self.assertFalse(data["is_onboarded"])

    def test_student_profile_includes_roll_and_level(self):
        from accounts.models import Student

        student = Student.objects.create(
            full_name="Nischal Karki",
            roll_number="078BEL101",
            academic_level="UG",
            department=self.department,
        )
        user = User.objects.create_user(
            email="078bel101.hari@pcampus.edu.np", password="secret123", person=student
        )

        profile = self._me(user)["profile"]
        self.assertEqual(profile["kind"], "student")
        self.assertEqual(profile["roll_number"], "078BEL101")
        self.assertEqual(profile["academic_level"], "UG")
        self.assertEqual(profile["department"], "Electronics Engineering")

    def test_faculty_profile_includes_designation(self):
        from accounts.models import Faculty

        faculty = Faculty.objects.create(
            full_name="Bikal Adhikari",
            designation="Assistant Professor",
            title="Dr.",
            department=self.department,
        )
        user = User.objects.create_user(
            email="bikal@pcampus.edu.np", password="secret123", person=faculty
        )

        profile = self._me(user)["profile"]
        self.assertEqual(profile["kind"], "faculty")
        self.assertEqual(profile["designation"], "Assistant Professor")
        self.assertEqual(profile["title"], "Dr.")

    def test_profile_is_read_only(self):
        # Every field on the serializer is declared read-only, so a client
        # cannot use this endpoint to mutate an account.
        from accounts.serializers import UserSerializer

        serializer = UserSerializer()
        self.assertTrue(all(field.read_only for field in serializer.fields.values()))


class OnboardingRoleSelectionTests(TestCase):
    """
    A role that carries power cannot be self-assigned. Onboarding records
    the request; an existing administrator grants it.
    """

    def setUp(self):
        from organization.models import Campus, Department
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.department = Department.objects.create(name="Dept R", campus=campus)
        self.admin = User.objects.create_user(
            email="root@pcampus.edu.np", password="secret123",
            is_staff=True, is_superuser=True, role="admin",
        )

    def _client(self, user):
        from rest_framework.test import APIClient
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    def _onboard(self, email, payload):
        user = User.objects.create_user(email=email, password="secret123")
        response = self._client(user).post(
            reverse("acocunts_apis:complete_profile"), payload, format="json"
        )
        self.assertEqual(response.status_code, 200, response.data)
        user.refresh_from_db()
        return user, response.data["data"]

    def test_student_is_granted_immediately_with_no_staff_flags(self):
        user, data = self._onboard("a@pcampus.edu.np", {
            "role": "student", "full_name": "Aarav Student",
            "academic_level": "UG", "roll_number": "080BCT001",
            "department_id": self.department.id,
        })
        self.assertEqual(user.role, "student")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertIsNone(data["pending_role"])
        self.assertIsNotNone(user.person)

    def test_choosing_admin_does_not_grant_anything(self):
        user, data = self._onboard("b@pcampus.edu.np", {
            "role": "admin", "full_name": "Bina Hopeful",
            "designation": "Coordinator", "department_id": self.department.id,
        })
        self.assertEqual(user.role, "student")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(data["pending_role"], "admin")
        self.assertTrue(
            RoleElevationRequest.objects.filter(
                user=user, requested_role="admin", status="PENDING"
            ).exists()
        )

    def test_choosing_faculty_is_also_gated(self):
        """is_staff alone makes a reviewer, so faculty is gated too."""
        user, data = self._onboard("c@pcampus.edu.np", {
            "role": "faculty", "full_name": "Chandra Hopeful",
            "designation": "Assistant Professor", "department_id": self.department.id,
        })
        self.assertFalse(user.is_staff)
        self.assertEqual(data["pending_role"], "faculty")

    def test_only_administrators_are_notified_of_a_role_request(self):
        reviewer = User.objects.create_user(
            email="reviewer@pcampus.edu.np", password="secret123", is_staff=True
        )
        user, _ = self._onboard("d@pcampus.edu.np", {
            "role": "admin", "full_name": "Deepa Hopeful",
            "designation": "Coordinator", "department_id": self.department.id,
        })
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin,
                notification_type=Notification.NotificationType.ROLE_REQUESTED,
            ).exists()
        )
        # A staff reviewer is not an administrator and cannot grant roles,
        # so telling them would be noise.
        self.assertFalse(Notification.objects.filter(recipient=reviewer).exists())

    def test_a_non_admin_cannot_decide_a_role_request(self):
        user, _ = self._onboard("e@pcampus.edu.np", {
            "role": "admin", "full_name": "Esha Hopeful",
            "designation": "Coordinator", "department_id": self.department.id,
        })
        elevation = RoleElevationRequest.objects.get(user=user)
        reviewer = User.objects.create_user(
            email="staffonly@pcampus.edu.np", password="secret123", is_staff=True
        )

        for actor in (user, reviewer):
            response = self._client(actor).post(
                reverse("acocunts_apis:role-request-decision", args=[elevation.id, "approve"])
            )
            self.assertEqual(response.status_code, 403, actor.email)

        user.refresh_from_db()
        self.assertFalse(user.is_superuser)

    def test_administrator_approval_grants_the_role(self):
        user, _ = self._onboard("f@pcampus.edu.np", {
            "role": "admin", "full_name": "Farhan Hopeful",
            "designation": "Coordinator", "department_id": self.department.id,
        })
        elevation = RoleElevationRequest.objects.get(user=user)

        response = self._client(self.admin).post(
            reverse("acocunts_apis:role-request-decision", args=[elevation.id, "approve"])
        )
        self.assertEqual(response.status_code, 200, response.data)

        user.refresh_from_db()
        self.assertEqual(user.role, "admin")
        self.assertTrue(user.is_staff)
        self.assertTrue(user.is_superuser)
        self.assertTrue(
            Notification.objects.filter(
                recipient=user,
                notification_type=Notification.NotificationType.ROLE_APPROVED,
            ).exists()
        )

    def test_faculty_approval_grants_staff_but_not_superuser(self):
        user, _ = self._onboard("g@pcampus.edu.np", {
            "role": "faculty", "full_name": "Gita Hopeful",
            "designation": "Lecturer", "department_id": self.department.id,
        })
        elevation = RoleElevationRequest.objects.get(user=user)
        self._client(self.admin).post(
            reverse("acocunts_apis:role-request-decision", args=[elevation.id, "approve"])
        )

        user.refresh_from_db()
        self.assertTrue(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_declining_leaves_the_account_unprivileged(self):
        user, _ = self._onboard("h@pcampus.edu.np", {
            "role": "admin", "full_name": "Hari Hopeful",
            "designation": "Coordinator", "department_id": self.department.id,
        })
        elevation = RoleElevationRequest.objects.get(user=user)
        self._client(self.admin).post(
            reverse("acocunts_apis:role-request-decision", args=[elevation.id, "decline"])
        )

        user.refresh_from_db()
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(
            Notification.objects.filter(
                recipient=user,
                notification_type=Notification.NotificationType.ROLE_DECLINED,
            ).exists()
        )

    def test_a_letter_prefixed_address_can_still_onboard_as_a_student(self):
        user, _ = self._onboard("sita@pcampus.edu.np", {
            "role": "student", "full_name": "Sita Student",
            "academic_level": "UG", "roll_number": "080BCT102",
            "department_id": self.department.id,
        })
        self.assertEqual(user.role, "student")
        self.assertEqual(user.person.student.roll_number, "080BCT102")
