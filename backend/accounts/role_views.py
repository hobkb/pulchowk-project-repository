"""
Approval of privileged-role requests.

Only an existing superuser may grant these: `is_staff` alone makes someone
a reviewer, so allowing a reviewer to grant roles would let privilege
spread sideways without an administrator ever being involved.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from core.responses import paginated_response, success_response
from notifications.services import NotificationService

from .models import RoleElevationRequest, UserRole


# What each granted role turns on.
ROLE_FLAGS = {
    UserRole.STUDENT: {"is_staff": False, "is_superuser": False},
    UserRole.FACULTY: {"is_staff": True, "is_superuser": False},
    UserRole.ADMIN: {"is_staff": True, "is_superuser": True},
}


class IsSuperUser(permissions.BasePermission):
    message = "Only an administrator can decide role requests."

    def has_permission(self, request, view):
        return bool(
            request.user
            and request.user.is_authenticated
            and request.user.is_superuser
        )


def serialize(elevation):
    return {
        "id": elevation.id,
        "user_email": elevation.user.email,
        "user_name": (
            f"{elevation.user.first_name} {elevation.user.last_name}".strip()
            or elevation.user.email
        ),
        "requested_role": elevation.requested_role,
        "reason": elevation.reason,
        "status": elevation.status,
        "created_at": elevation.created_at,
        "decided_at": elevation.decided_at,
    }


class RoleRequestQueueView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperUser]

    def get(self, request):
        rows = RoleElevationRequest.objects.select_related("user").order_by("-created_at")
        wanted = (request.query_params.get("status") or "").strip().upper()
        if wanted in RoleElevationRequest.Status.values:
            rows = rows.filter(status=wanted)
        return paginated_response(
            request,
            rows,
            lambda page: [serialize(r) for r in page],
            page_size=5,
        )


class RoleRequestDecisionView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsSuperUser]

    def post(self, request, request_id, decision):
        elevation = get_object_or_404(
            RoleElevationRequest.objects.select_related("user"), id=request_id
        )
        if elevation.status != RoleElevationRequest.Status.PENDING:
            raise ValidationError(
                {"detail": f"This request has already been {elevation.status.lower()}."}
            )

        approved = decision == "approve"
        elevation.status = (
            RoleElevationRequest.Status.APPROVED
            if approved
            else RoleElevationRequest.Status.DECLINED
        )
        elevation.decided_by = request.user
        elevation.decided_at = timezone.now()
        elevation.save(update_fields=["status", "decided_by", "decided_at"])

        if approved:
            flags = ROLE_FLAGS.get(elevation.requested_role, ROLE_FLAGS[UserRole.STUDENT])
            target = elevation.user
            target.role = elevation.requested_role
            target.is_staff = flags["is_staff"]
            target.is_superuser = flags["is_superuser"]
            target.save(update_fields=["role", "is_staff", "is_superuser"])

        NotificationService.notify_role_decision(elevation)

        return success_response(
            data=serialize(elevation),
            message=f"Role request {elevation.status.lower()}.",
        )


class MyRoleRequestView(APIView):
    """Lets the applicant see where their own request stands."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        latest = (
            RoleElevationRequest.objects.filter(user=request.user)
            .order_by("-created_at")
            .first()
        )
        return success_response(data=serialize(latest) if latest else None)
