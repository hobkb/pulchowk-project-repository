from django.contrib.auth import get_user_model
from django.db.models import Q

from .models import Notification

User = get_user_model()


def _admin_recipients():
    """
    Every user who can review an ingestion job: global admins/staff, or an
    active department admin. Expressed as a queryset (rather than looping
    every user through ingestion.views.is_admin_or_dept_admin, which checks
    one user at a time) but the underlying rule is the same one already
    used to gate the review endpoints.
    """
    from organization.models import DepartmentAdmin

    dept_admin_person_ids = DepartmentAdmin.objects.filter(is_active=True).values_list(
        "faculty_id", flat=True
    )
    return User.objects.filter(
        Q(is_staff=True) | Q(is_superuser=True) | Q(role="admin") | Q(person_id__in=dept_admin_person_ids)
    ).distinct()


class NotificationService:
    """
    The only place Notification rows get created. Each method is a thin,
    single-purpose wrapper around one real ingestion-job lifecycle event --
    called directly from the pipeline runner / publish view, not from a
    signal, so the call sites stay easy to find.
    """

    @staticmethod
    def notify_job_ready_for_review(job):
        Notification.objects.create(
            recipient=job.uploaded_by,
            notification_type=Notification.NotificationType.JOB_READY_FOR_REVIEW,
            message=f'Your upload "{job.original_filename}" has been processed and is ready for review.',
            job=job,
        )

    @staticmethod
    def notify_job_awaiting_admin(job):
        recipients = _admin_recipients()
        if not recipients.exists():
            return
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient=admin,
                    notification_type=Notification.NotificationType.JOB_AWAITING_ADMIN,
                    message=f'A new upload "{job.original_filename}" is awaiting review.',
                    job=job,
                )
                for admin in recipients
            ]
        )

    @staticmethod
    def notify_job_failed(job):
        Notification.objects.create(
            recipient=job.uploaded_by,
            notification_type=Notification.NotificationType.JOB_FAILED,
            message=f'Processing failed for your upload "{job.original_filename}".',
            job=job,
        )

    @staticmethod
    def notify_job_published(job, project):
        Notification.objects.create(
            recipient=job.uploaded_by,
            notification_type=Notification.NotificationType.JOB_PUBLISHED,
            message=f'Your project "{project.title}" has been published to the repository.',
            job=job,
            project=project,
        )

    # ---- Report access requests -------------------------------------

    @staticmethod
    def notify_access_requested(access_request):
        """Tells every reviewer that someone has asked for a full report."""
        recipients = _admin_recipients()
        if not recipients.exists():
            return
        who = access_request.requester.email
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient=admin,
                    notification_type=Notification.NotificationType.ACCESS_REQUESTED,
                    message=f'{who} requested the full report for "{access_request.project.title}".',
                    project=access_request.project,
                    actor=access_request.requester,
                )
                for admin in recipients
            ]
        )

    @staticmethod
    def notify_access_decision(access_request):
        """Tells the requester the outcome, the moment it is decided."""
        approved = access_request.status == access_request.Status.APPROVED
        if approved:
            message = (
                f'Your request for "{access_request.project.title}" was approved. '
                "The full report is now available to you."
            )
            kind = Notification.NotificationType.ACCESS_APPROVED
        else:
            message = f'Your request for "{access_request.project.title}" was declined.'
            kind = Notification.NotificationType.ACCESS_DECLINED

        Notification.objects.create(
            recipient=access_request.requester,
            notification_type=kind,
            message=message,
            project=access_request.project,
        )

    # ---- Role elevation ---------------------------------------------

    @staticmethod
    def notify_role_requested(elevation):
        """Only existing administrators are told, since only they can grant
        it -- a faculty reviewer must not be able to mint more admins."""
        admins = User.objects.filter(is_superuser=True).distinct()
        if not admins.exists():
            return
        Notification.objects.bulk_create(
            [
                Notification(
                    recipient=admin,
                    notification_type=Notification.NotificationType.ROLE_REQUESTED,
                    message=(
                        f"{elevation.user.email} has asked for "
                        f"{elevation.requested_role} access."
                    ),
                )
                for admin in admins
            ]
        )

    @staticmethod
    def notify_role_decision(elevation):
        approved = elevation.status == elevation.Status.APPROVED
        Notification.objects.create(
            recipient=elevation.user,
            notification_type=(
                Notification.NotificationType.ROLE_APPROVED
                if approved
                else Notification.NotificationType.ROLE_DECLINED
            ),
            message=(
                f"Your request for {elevation.requested_role} access was approved. "
                "Sign out and back in to pick up your new permissions."
                if approved
                else f"Your request for {elevation.requested_role} access was declined."
            ),
        )
