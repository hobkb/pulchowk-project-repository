"""
Reviewer-only project management and the report-access request flow.

Deliberately separate from views.py, which is the public read-only
catalogue. Everything here either requires reviewer rights or is scoped to
the requesting user.
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.views import APIView

from core.responses import paginated_response, success_response
from notifications.models import Notification
from notifications.services import NotificationService
from organization.departments import canonical_department
from organization.models import Department
from accounts.models import Faculty, Person
from ingestion.pipeline.utils.text_cleaners import normalize_person_name
from repository.models import (
    Keyword,
    Project,
    ProjectAccessRequest,
    ProjectKeyword,
    ProjectPerson,
)
from repository.serializers import ProjectDetailSerializer


def is_reviewer(user):
    """Staff, superusers, the admin role, or an active department admin --
    the same rule the ingestion review endpoints already use."""
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin":
        return True
    person_id = getattr(user, "person_id", None)
    if person_id is None:
        return False
    from organization.models import DepartmentAdmin

    return DepartmentAdmin.objects.filter(faculty_id=person_id, is_active=True).exists()


class IsReviewer(permissions.BasePermission):
    message = "This action is restricted to departmental administrators."

    def has_permission(self, request, view):
        return is_reviewer(request.user)


def serialize_access_request(access_request):
    return {
        "id": access_request.id,
        "project": access_request.project_id,
        "project_title": access_request.project.title,
        "requester_email": access_request.requester.email,
        "requester_name": (
            f"{access_request.requester.first_name} {access_request.requester.last_name}".strip()
            or access_request.requester.email
        ),
        "reason": access_request.reason,
        "status": access_request.status,
        "decision_note": access_request.decision_note,
        "decided_at": access_request.decided_at,
        "created_at": access_request.created_at,
    }


class ProjectAccessRequestCreateView(APIView):
    """A reader asks for one project's full report."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, project_id):
        project = get_object_or_404(Project, id=project_id, status="Published")

        existing = ProjectAccessRequest.objects.filter(
            project=project,
            requester=request.user,
            status__in=[
                ProjectAccessRequest.Status.PENDING,
                ProjectAccessRequest.Status.APPROVED,
            ],
        ).first()
        if existing:
            # Re-asking while one is open (or already granted) would only
            # spam reviewers; report the existing one instead of erroring.
            return success_response(
                data=serialize_access_request(existing),
                message=(
                    "You already have access to this report."
                    if existing.is_granted
                    else "Your request is already awaiting a decision."
                ),
            )

        access_request = ProjectAccessRequest.objects.create(
            project=project,
            requester=request.user,
            reason=(request.data.get("reason") or "").strip()[:2000],
        )
        NotificationService.notify_access_requested(access_request)

        return success_response(
            data=serialize_access_request(access_request),
            message="Your request has been sent to the department.",
            status=status.HTTP_201_CREATED,
        )


class ProjectAccessRequestCancelView(APIView):
    """
    A reader withdraws their own pending request.

    The request is deleted rather than marked cancelled: a withdrawn ask
    is not a decision anyone needs to see, and leaving it in the queue
    would have reviewers acting on something no longer wanted. The
    notifications it raised go with it, so reviewers are not left holding
    a link to a request that no longer exists.

    Only a PENDING request can be withdrawn. An approved one is not the
    reader's to revoke -- that is the department's call -- and a declined
    one has already been acted on.
    """

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request, project_id):
        access_request = ProjectAccessRequest.objects.filter(
            project_id=project_id,
            requester=request.user,
            status=ProjectAccessRequest.Status.PENDING,
        ).first()

        if access_request is None:
            raise ValidationError(
                {"detail": "You have no pending request for this report."}
            )

        # The reviewers' copies of "someone asked for this report" go
        # with the request itself, so nobody is left holding a link to a
        # request that no longer exists.
        Notification.objects.filter(
            notification_type=Notification.NotificationType.ACCESS_REQUESTED,
            project_id=project_id,
            actor=request.user,
        ).delete()

        access_request.delete()

        return success_response(
            data={"project": project_id, "status": "none"},
            message="Your request has been withdrawn.",
        )


class MyAccessRequestsView(APIView):
    """The signed-in user's own requests, so the project page can show
    their state without exposing anyone else's."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        rows = (
            ProjectAccessRequest.objects.filter(requester=request.user)
            .select_related("project", "requester")
            .order_by("-created_at")
        )
        return paginated_response(
            request,
            rows,
            lambda page: [serialize_access_request(r) for r in page],
            page_size=5,
        )


class AccessRequestQueueView(APIView):
    """Every request, for reviewers to act on."""

    permission_classes = [permissions.IsAuthenticated, IsReviewer]

    def get(self, request):
        rows = ProjectAccessRequest.objects.select_related(
            "project", "requester"
        ).order_by("-created_at")

        requested_status = (request.query_params.get("status") or "").strip().upper()
        if requested_status in ProjectAccessRequest.Status.values:
            rows = rows.filter(status=requested_status)

        return paginated_response(
            request,
            rows,
            lambda page: [serialize_access_request(r) for r in page],
            page_size=5,
        )


class AccessRequestDecisionView(APIView):
    """Approve or decline one request. The requester is notified either
    way, and an approval immediately unlocks the report for them."""

    permission_classes = [permissions.IsAuthenticated, IsReviewer]

    def post(self, request, request_id, decision):
        access_request = get_object_or_404(
            ProjectAccessRequest.objects.select_related("project", "requester"),
            id=request_id,
        )
        if access_request.status != ProjectAccessRequest.Status.PENDING:
            raise ValidationError(
                {"detail": f"This request has already been {access_request.status.lower()}."}
            )

        access_request.status = (
            ProjectAccessRequest.Status.APPROVED
            if decision == "approve"
            else ProjectAccessRequest.Status.DECLINED
        )
        access_request.decided_by = request.user
        access_request.decided_at = timezone.now()
        access_request.decision_note = (request.data.get("note") or "").strip()[:2000]
        access_request.save(
            update_fields=["status", "decided_by", "decided_at", "decision_note", "updated_at"]
        )

        NotificationService.notify_access_decision(access_request)

        return success_response(
            data=serialize_access_request(access_request),
            message=f"Request {access_request.status.lower()}.",
        )


SUPERVISORY_ROLES = ("Supervisor", "Co-Supervisor")


def _replace_supervisors(project, supplied):
    """Sets this project's supervisors to exactly the list supplied.

    Each entry is matched to an existing Faculty record by name before any
    new one is created, so naming a supervisor already in the directory
    links to that same person rather than creating a second record -- which
    would split their project list across two entries in the search facet.

    Author links are untouched: only the supervisory roles are replaced.
    """
    resolved = []
    for entry in supplied:
        if isinstance(entry, str):
            entry = {"full_name": entry}
        if not isinstance(entry, dict):
            continue

        full_name = normalize_person_name(str(entry.get("full_name") or "").strip())
        if not full_name:
            continue

        title = str(entry.get("title") or "").strip()
        designation = str(entry.get("designation") or "").strip()
        role = str(entry.get("role") or "Supervisor").strip()
        if role not in SUPERVISORY_ROLES:
            role = "Supervisor"

        faculty = Faculty.objects.filter(full_name__iexact=full_name).first()
        if faculty is None:
            # Person -> Faculty is table-per-type, so a plain Person holding
            # this name cannot be turned into one; reporting that is better
            # than raising an opaque database error.
            if Person.objects.filter(full_name__iexact=full_name).exists():
                raise ValidationError({
                    "supervisors": f'"{full_name}" is already recorded as a non-faculty person.'
                })
            faculty = Faculty.objects.create(
                full_name=full_name,
                title=title,
                designation=designation,
                department=project.department,
            )
        else:
            # Additive: a blank field here never clears what is on record.
            fills = {}
            if title and title != faculty.title:
                fills["title"] = title
            if designation and designation != faculty.designation:
                fills["designation"] = designation
            if project.department_id and faculty.department_id is None:
                fills["department"] = project.department
            if fills:
                for field, value in fills.items():
                    setattr(faculty, field, value)
                faculty.save(update_fields=list(fills))

        resolved.append((faculty, role))

    ProjectPerson.objects.filter(project=project, role__in=SUPERVISORY_ROLES).delete()

    next_order = (
        project.project_people.order_by("-display_order")
        .values_list("display_order", flat=True)
        .first()
        or 0
    )
    seen = set()
    for faculty, role in resolved:
        if (faculty.pk, role) in seen:
            continue
        seen.add((faculty.pk, role))
        next_order += 1
        ProjectPerson.objects.create(
            project=project, person=faculty, role=role, display_order=next_order
        )


class ProjectManageView(APIView):
    """Reviewer-only edit and delete for a published project.

    Only catalogue metadata is editable here -- the extracted report body
    is not, because correcting that belongs in the ingestion review
    workflow where the source PDF is alongside it.
    """

    permission_classes = [permissions.IsAuthenticated, IsReviewer]

    EDITABLE = {
        "title",
        "abstract",
        "academic_level",
        "project_type",
        "batch",
        "cluster",
        "language",
        "github_url",
        "doi_url",
        "publication_url",
        "demo_url",
    }

    def patch(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        data = request.data or {}
        errors = {}
        updates = {}

        for field in self.EDITABLE:
            if field not in data:
                continue
            value = data[field]
            if isinstance(value, str):
                value = value.strip()
            updates[field] = value

        if "title" in updates and not updates["title"]:
            errors["title"] = "Title cannot be empty."

        if updates.get("cluster"):
            valid = {c[0] for c in Project.CLUSTERS}
            candidate = str(updates["cluster"]).upper()
            if candidate not in valid:
                errors["cluster"] = "Not a recognised cluster."
            else:
                updates["cluster"] = candidate
        elif "cluster" in updates:
            updates["cluster"] = None

        if updates.get("academic_level") and updates["academic_level"] not in [
            c[0] for c in Project.ACADEMIC_LEVELS
        ]:
            errors["academic_level"] = "Not a recognised academic level."

        if updates.get("project_type") and updates["project_type"] not in [
            c[0] for c in Project.PROJECT_TYPES
        ]:
            errors["project_type"] = "Not a recognised project type."

        # Department arrives as a name and is resolved against the real six.
        if "department_name" in data:
            raw = (data.get("department_name") or "").strip()
            if raw:
                canonical = canonical_department(raw) or raw
                department = Department.objects.filter(name__iexact=canonical).first()
                if department is None:
                    errors["department_name"] = "Not a recognised department."
                else:
                    project.department = department
            else:
                project.department = None

        if errors:
            raise ValidationError(errors)

        for field, value in updates.items():
            setattr(project, field, value)
        project.save()

        # Keywords are replaced wholesale when supplied.
        if isinstance(data.get("keywords"), list):
            ProjectKeyword.objects.filter(project=project).delete()
            for name in data["keywords"]:
                name = str(name).strip()
                if not name:
                    continue
                keyword, _ = Keyword.objects.get_or_create(name=name)
                ProjectKeyword.objects.get_or_create(project=project, keyword=keyword)

        # Supervisors are replaced wholesale when supplied. A supervisor is
        # often only identified after publication -- the report names them
        # nowhere extraction could find, and someone recognises them later.
        if isinstance(data.get("supervisors"), list):
            _replace_supervisors(project, data["supervisors"])

        project.refresh_from_db()
        return success_response(
            data=ProjectDetailSerializer(project, context={"request": request}).data,
            message="Project updated.",
        )

    def delete(self, request, project_id):
        project = get_object_or_404(Project, id=project_id)
        # Deleting the catalogue record must not delete the deposit it came
        # from: the ingestion job and its PDF stay, so the project can be
        # republished from the source if this was a mistake.
        title = project.title
        project.delete()
        return success_response(
            data={"deleted": project_id},
            message=f'"{title}" has been removed from the catalogue.',
        )
