"""
Withdrawing a report-access request.

A reader who changes their mind should be able to take the ask back, and
the reviewers' copies of it should go with it rather than lingering as a
link to something that no longer exists.
"""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from notifications.models import Notification
from organization.models import Campus, Department
from repository.models import Project, ProjectAccessRequest


class CancelAccessRequestTests(APITestCase):
    def setUp(self):
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.dept = Department.objects.create(name="Dept C", campus=campus)
        self.project = Project.objects.create(
            title="Some Project", status="Published", department=self.dept
        )
        self.admin = User.objects.create_user(
            email="admin-c@pcampus.edu.np", password="x",
            is_staff=True, is_superuser=True, role="admin",
        )
        self.reader = User.objects.create_user(
            email="reader-c@pcampus.edu.np", password="x"
        )

    def request_access(self, user):
        self.client.force_authenticate(user=user)
        return self.client.post(
            reverse("repository:access-request-create", args=[self.project.id]),
            {"reason": "for reference"},
            format="json",
        )

    def cancel(self, user):
        self.client.force_authenticate(user=user)
        return self.client.delete(
            reverse("repository:access-request-cancel", args=[self.project.id])
        )

    def test_a_pending_request_can_be_withdrawn(self):
        self.request_access(self.reader)
        self.assertTrue(ProjectAccessRequest.objects.filter(requester=self.reader).exists())

        response = self.cancel(self.reader)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertFalse(ProjectAccessRequest.objects.filter(requester=self.reader).exists())

    def test_withdrawing_removes_the_reviewers_notifications(self):
        self.request_access(self.reader)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.admin,
                notification_type=Notification.NotificationType.ACCESS_REQUESTED,
            ).exists()
        )

        self.cancel(self.reader)
        self.assertFalse(
            Notification.objects.filter(
                notification_type=Notification.NotificationType.ACCESS_REQUESTED,
                project=self.project,
                actor=self.reader,
            ).exists()
        )

    def test_withdrawing_leaves_another_readers_request_alone(self):
        other = User.objects.create_user(email="other-c@pcampus.edu.np", password="x")
        self.request_access(other)
        self.request_access(self.reader)

        self.cancel(self.reader)

        self.assertTrue(ProjectAccessRequest.objects.filter(requester=other).exists())
        self.assertTrue(
            Notification.objects.filter(
                notification_type=Notification.NotificationType.ACCESS_REQUESTED,
                actor=other,
            ).exists()
        )

    def test_an_approved_request_is_not_the_readers_to_revoke(self):
        self.request_access(self.reader)
        access_request = ProjectAccessRequest.objects.get(requester=self.reader)
        access_request.status = ProjectAccessRequest.Status.APPROVED
        access_request.save(update_fields=["status"])

        response = self.cancel(self.reader)
        self.assertEqual(response.status_code, 400, response.data)
        access_request.refresh_from_db()
        self.assertEqual(access_request.status, ProjectAccessRequest.Status.APPROVED)

    def test_cancelling_without_a_request_is_reported_not_crashed(self):
        response = self.cancel(self.reader)
        self.assertEqual(response.status_code, 400, response.data)

    def test_requesting_again_after_withdrawing_works(self):
        self.request_access(self.reader)
        self.cancel(self.reader)
        response = self.request_access(self.reader)
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(
            ProjectAccessRequest.objects.filter(requester=self.reader).count(), 1
        )
