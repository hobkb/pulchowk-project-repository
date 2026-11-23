"""Clearing all of the signed-in user's notifications."""

from django.urls import reverse
from rest_framework.test import APITestCase

from accounts.models import User
from notifications.models import Notification


class ClearAllNotificationsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="clear-a@pcampus.edu.np", password="x")
        self.other = User.objects.create_user(email="clear-b@pcampus.edu.np", password="x")

    def _notify(self, recipient, n=1):
        for _ in range(n):
            Notification.objects.create(
                recipient=recipient,
                notification_type=Notification.NotificationType.JOB_PUBLISHED,
                message="x",
            )

    def test_clears_only_the_requesters_own_notifications(self):
        self._notify(self.user, 3)
        self._notify(self.other, 2)

        self.client.force_authenticate(user=self.user)
        response = self.client.delete(reverse("notifications:notification-clear-all"))

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["deleted"], 3)
        self.assertEqual(Notification.objects.filter(recipient=self.user).count(), 0)
        self.assertEqual(Notification.objects.filter(recipient=self.other).count(), 2)

    def test_clearing_with_nothing_to_clear_is_not_an_error(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.delete(reverse("notifications:notification-clear-all"))
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["deleted"], 0)

    def test_requires_authentication(self):
        response = self.client.delete(reverse("notifications:notification-clear-all"))
        self.assertEqual(response.status_code, 401)
