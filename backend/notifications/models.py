from django.conf import settings
from django.db import models


class Notification(models.Model):
    """
    A single notification tied to a real ingestion-job lifecycle event.

    Deliberately minimal: no generic/polymorphic target. Just the two
    optional FKs (`job`, `project`) needed so the frontend can build the
    right link without an extra API call -- a job is linked while it's
    still in the admin review pipeline, a project once it's published.
    """

    class NotificationType(models.TextChoices):
        JOB_READY_FOR_REVIEW = "JOB_READY_FOR_REVIEW", "Job ready for review"
        JOB_AWAITING_ADMIN = "JOB_AWAITING_ADMIN", "Job awaiting admin review"
        JOB_FAILED = "JOB_FAILED", "Job failed"
        JOB_PUBLISHED = "JOB_PUBLISHED", "Job published"
        ACCESS_REQUESTED = "ACCESS_REQUESTED", "Report access requested"
        ACCESS_APPROVED = "ACCESS_APPROVED", "Report access approved"
        ACCESS_DECLINED = "ACCESS_DECLINED", "Report access declined"
        ROLE_REQUESTED = "ROLE_REQUESTED", "Role access requested"
        ROLE_APPROVED = "ROLE_APPROVED", "Role access approved"
        ROLE_DECLINED = "ROLE_DECLINED", "Role access declined"

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        db_index=True,
    )
    notification_type = models.CharField(max_length=30, choices=NotificationType.choices)
    # Who caused this notice, when someone did. Needed so a notice can be
    # withdrawn along with the action that raised it -- matching on the
    # message text would break the moment the wording changed.
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_triggered",
    )
    message = models.CharField(max_length=255)
    job = models.ForeignKey(
        "ingestion.IngestionJob",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notifications",
    )
    project = models.ForeignKey(
        "repository.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Notification({self.id}, {self.notification_type}, recipient={self.recipient_id})"
