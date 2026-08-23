from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import Faculty, User
from ingestion.models import IngestionJob
from ingestion.pipeline.runner import PipelineRunner
from notifications.models import Notification
from notifications.services import NotificationService
from organization.models import Campus, Department, DepartmentAdmin


def _make_job(uploaded_by, **kwargs):
    return IngestionJob.objects.create(
        file=SimpleUploadedFile("report.pdf", b"%PDF-1.4", content_type="application/pdf"),
        original_filename="report.pdf",
        uploaded_by=uploaded_by,
        **kwargs,
    )


class RunnerNotificationTriggerTests(TestCase):
    """
    PipelineRunner.execute() runs real PDF-extraction steps, which is
    unnecessary overhead for testing purely that the right notifications
    fire on the right status transition -- STEPS is monkeypatched to a
    trivial fake step so only execute()'s own success/exception branches
    are exercised.
    """

    def test_extracted_notifies_uploader_and_admins(self):
        uploader = User.objects.create_user(email="uploader@example.com", password="secret123")
        admin = User.objects.create_user(email="admin@example.com", password="secret123", is_staff=True)
        job = _make_job(uploader)

        class FakeStep:
            def run(self, job, context):
                context["draft_metadata"] = {"project_fields": {"title": "X"}}
                return context

        with patch.object(PipelineRunner, "STEPS", [FakeStep()]):
            PipelineRunner().execute(job)

        job.refresh_from_db()
        self.assertEqual(job.status, IngestionJob.Status.EXTRACTED)

        uploader_notifs = Notification.objects.filter(recipient=uploader, job=job)
        self.assertEqual(uploader_notifs.count(), 1)
        self.assertEqual(
            uploader_notifs.first().notification_type,
            Notification.NotificationType.JOB_READY_FOR_REVIEW,
        )

        admin_notifs = Notification.objects.filter(recipient=admin, job=job)
        self.assertEqual(admin_notifs.count(), 1)
        self.assertEqual(
            admin_notifs.first().notification_type,
            Notification.NotificationType.JOB_AWAITING_ADMIN,
        )

    def test_failed_notifies_uploader_only(self):
        uploader = User.objects.create_user(email="uploader2@example.com", password="secret123")
        job = _make_job(uploader)

        class FailingStep:
            def run(self, job, context):
                raise ValueError("boom")

        with patch.object(PipelineRunner, "STEPS", [FailingStep()]):
            with self.assertRaises(ValueError):
                PipelineRunner().execute(job)

        job.refresh_from_db()
        self.assertEqual(job.status, IngestionJob.Status.FAILED)

        notifs = Notification.objects.filter(recipient=uploader, job=job)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, Notification.NotificationType.JOB_FAILED)


class PublishNotificationTriggerTests(TestCase):
    def setUp(self):
        self.campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        self.department = Department.objects.create(name="Computer Engineering", campus=self.campus)

    def _extracted_job(self, uploader, sections_skipped=False):
        payload = {
            "project_fields": {
                "title": "Notification Test Project",
                "abstract": "Abstract.",
                "department_name": self.department.name,
                "campus_name": self.campus.name,
            },
            "people_and_roles": [{"full_name": "Alice Example", "role": "Author"}],
            "project_sections": [],
        }
        if sections_skipped:
            payload["_sections_skipped"] = True
        return _make_job(uploader, status=IngestionJob.Status.EXTRACTED, extracted_payload=payload)

    def test_publish_notifies_uploader(self):
        uploader = User.objects.create_user(email="pub1@example.com", password="secret123")
        admin = User.objects.create_user(email="pubadmin1@example.com", password="secret123", is_staff=True)
        job = self._extracted_job(uploader)

        client = APIClient()
        client.force_authenticate(user=admin)
        response = client.post(reverse("ingestion:job-publish", args=[job.id]))

        self.assertEqual(response.status_code, 200, response.data)
        job.refresh_from_db()

        notifs = Notification.objects.filter(recipient=uploader, job=job)
        self.assertEqual(notifs.count(), 1)
        self.assertEqual(notifs.first().notification_type, Notification.NotificationType.JOB_PUBLISHED)
        self.assertEqual(notifs.first().project, job.published_project)

    def test_sections_pending_republish_notifies_uploader_again(self):
        uploader = User.objects.create_user(email="pub2@example.com", password="secret123")
        admin = User.objects.create_user(email="pubadmin2@example.com", password="secret123", is_staff=True)
        job = self._extracted_job(uploader, sections_skipped=True)

        client = APIClient()
        client.force_authenticate(user=admin)
        first = client.post(reverse("ingestion:job-publish", args=[job.id]))
        self.assertEqual(first.status_code, 200, first.data)
        job.refresh_from_db()
        self.assertEqual(job.status, IngestionJob.Status.SECTIONS_PENDING)

        job.extracted_payload["project_sections"] = [
            {"heading": "Introduction", "heading_level": 1, "display_order": 1, "content": "Body."}
        ]
        job.save(update_fields=["extracted_payload"])

        second = client.post(reverse("ingestion:job-publish", args=[job.id]))
        self.assertEqual(second.status_code, 200, second.data)
        job.refresh_from_db()
        self.assertEqual(job.status, IngestionJob.Status.VERIFIED)

        notifs = Notification.objects.filter(recipient=uploader, job=job)
        self.assertEqual(notifs.count(), 2)
        self.assertTrue(
            all(n.notification_type == Notification.NotificationType.JOB_PUBLISHED for n in notifs)
        )


class AdminRecipientFanoutTests(TestCase):
    def test_department_admin_is_included_in_fanout(self):
        uploader = User.objects.create_user(email="uploader3@example.com", password="secret123")
        campus = Campus.objects.get_or_create(name="Pulchowk Campus")[0]
        department = Department.objects.create(name="Computer Engineering", campus=campus)
        faculty = Faculty.objects.create(full_name="Dr. Dept Admin", department=department)
        dept_admin_user = User.objects.create_user(
            email="deptadmin@example.com", password="secret123", person=faculty
        )
        DepartmentAdmin.objects.create(faculty=faculty, department=department, is_active=True)

        job = _make_job(uploader)
        NotificationService.notify_job_awaiting_admin(job)

        self.assertTrue(
            Notification.objects.filter(recipient=dept_admin_user, job=job).exists()
        )


class NotificationAPITests(TestCase):
    def setUp(self):
        self.user_a = User.objects.create_user(email="a@example.com", password="secret123")
        self.user_b = User.objects.create_user(email="b@example.com", password="secret123")
        self.notif = Notification.objects.create(
            recipient=self.user_a,
            notification_type=Notification.NotificationType.JOB_READY_FOR_REVIEW,
            message="Test notification",
        )

    def test_list_returns_only_own_notifications(self):
        Notification.objects.create(
            recipient=self.user_b,
            notification_type=Notification.NotificationType.JOB_READY_FOR_REVIEW,
            message="Someone else's notification",
        )
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        response = client.get(reverse("notifications:notification-list"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

    def test_unread_count(self):
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        response = client.get(reverse("notifications:notification-unread-count"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["count"], 1)

    def test_mark_read(self):
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        response = client.post(reverse("notifications:notification-mark-read", args=[self.notif.id]))
        self.assertEqual(response.status_code, 200)
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.is_read)

    def test_mark_read_rejects_other_users_notification(self):
        client = APIClient()
        client.force_authenticate(user=self.user_b)
        response = client.post(reverse("notifications:notification-mark-read", args=[self.notif.id]))
        self.assertEqual(response.status_code, 404)
        self.notif.refresh_from_db()
        self.assertFalse(self.notif.is_read)

    def test_mark_all_read(self):
        Notification.objects.create(
            recipient=self.user_a,
            notification_type=Notification.NotificationType.JOB_FAILED,
            message="Second one",
        )
        client = APIClient()
        client.force_authenticate(user=self.user_a)
        response = client.post(reverse("notifications:notification-mark-all-read"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["updated"], 2)
        self.assertEqual(self.user_a.notifications.filter(is_read=False).count(), 0)
