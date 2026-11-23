"""
Self-service editing of the signed-in user's own profile.

What a person may change about themselves is deliberately narrow. Identity
-- the email address, the roll number proven by that address, and the role
-- is set by the institution or by an administrator, never by the account
holder. Everything here is presentation detail they are the best source for.
"""

from rest_framework import permissions
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from core.responses import success_response
from organization.models import Department, ResearchGroup

from .models import Faculty, Student
from .serializers import UserSerializer
from .services import ProfileService
from ingestion.pipeline.utils.text_cleaners import (
    ROLL_PATTERN,
    clean_roll_number,
    normalize_person_name,
)


class MyProfileView(APIView):
    """PATCH the fields the account holder legitimately owns."""

    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        user = request.user
        person = getattr(user, "person", None)
        if person is None:
            raise ValidationError(
                {"detail": "Complete onboarding before editing your profile."}
            )

        data = request.data
        updated = []

        # Person and Student/Faculty are separate rows joined by inheritance,
        # and `person.student` hands back a DIFFERENT Python object wrapping
        # the same pair of rows. Editing the parent object and then saving
        # the child writes the child's own stale copy of the shared columns,
        # silently dropping the edit -- so every field is applied to one
        # object, the most specific one that exists.
        target = getattr(person, "student", None) or getattr(person, "faculty", None) or person

        if "full_name" in data:
            name = normalize_person_name(str(data["full_name"]).strip())
            if not name:
                raise ValidationError({"full_name": "A name is required."})
            target.full_name = name
            updated.append("full_name")

        if "department_id" in data:
            department_id = data["department_id"]
            if department_id in (None, ""):
                target.department = None
            else:
                if not Department.objects.filter(id=department_id).exists():
                    raise ValidationError({"department_id": "Unknown department."})
                target.department_id = department_id
            updated.append("department")

        student = target if isinstance(target, Student) else None
        faculty = target if isinstance(target, Faculty) else None

        if student is not None:
            if "academic_level" in data:
                level = str(data["academic_level"])
                if level not in dict(Student.ACADEMIC_LEVELS):
                    raise ValidationError({"academic_level": "Unknown level."})
                student.academic_level = level
                updated.append("academic_level")

            # The roll number is only editable when the campus address does
            # not already prove one. Where it does, the submitted value is
            # ignored rather than rejected -- the field is disabled in the
            # UI, so anything arriving here is not a user correcting a typo.
            if "roll_number" in data and not ProfileService.verified_roll_number(user.email):
                roll = clean_roll_number(str(data["roll_number"]).strip())
                if not ROLL_PATTERN.fullmatch(roll or ""):
                    raise ValidationError(
                        {"roll_number": "Enter a roll number such as 080BCT083."}
                    )
                taken = (
                    Student.objects.filter(roll_number=roll)
                    .exclude(pk=student.pk)
                    .exists()
                )
                if taken:
                    raise ValidationError(
                        {"roll_number": f"Roll number {roll} belongs to another account."}
                    )
                student.roll_number = roll
                updated.append("roll_number")

        if faculty is not None:
            for field in ("title", "designation"):
                if field in data:
                    setattr(faculty, field, str(data[field]).strip()[:100])
                    updated.append(field)

            if "research_group_id" in data:
                group_id = data["research_group_id"]
                if group_id in (None, ""):
                    faculty.research_group = None
                elif ResearchGroup.objects.filter(id=group_id).exists():
                    faculty.research_group_id = group_id
                else:
                    raise ValidationError({"research_group_id": "Unknown research group."})
                updated.append("research_group")

        # Saving the subtype writes the parent row too.
        target.save()

        user.refresh_from_db()
        return success_response(
            data=UserSerializer(user).data,
            message="Profile updated." if updated else "Nothing to update.",
        )
