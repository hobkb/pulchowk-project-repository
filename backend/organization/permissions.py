from rest_framework.permissions import BasePermission

from .models import DepartmentAdmin


class IsDepartmentAdmin(BasePermission):
    """
    Allows access only to users who are recorded as active department admins.

    A user qualifies when their linked person is present in the
    department_admins table with is_active=True.
    """

    message = "You must be an active department admin to access this resource."

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False

        person = getattr(user, "person", None)
        if person is None:
            return False

        return DepartmentAdmin.objects.filter(
            faculty=person,
            is_active=True,
        ).exists()