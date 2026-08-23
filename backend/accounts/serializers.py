from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Student, Faculty
from .services import ProfileService

class FacultySerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ("id", "full_name", "title", "designation", "department_id", "email")


class FacultyCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Faculty
        fields = ("id", "full_name", "title", "designation", "department")


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ("id", "full_name", "roll_number", "academic_level", "department_id", "email")


class StudentOnboardingSerializer(serializers.Serializer):
    """
    Serializer for student onboarding profile completion.
    """
    full_name = serializers.CharField(max_length=255)
    academic_level = serializers.ChoiceField(choices=Student.ACADEMIC_LEVELS)
    roll_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)


class FacultyOnboardingSerializer(serializers.Serializer):
    """
    Serializer for faculty onboarding profile completion.
    """
    faculty_id = serializers.IntegerField(required=False, allow_null=True)
    full_name = serializers.CharField(max_length=255)
    title = serializers.CharField(max_length=50, required=False, allow_blank=True)
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    research_group_id = serializers.IntegerField(required=False, allow_null=True)


User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer representing the authenticated user.

    Returned by:
        - POST /api/accounts/google/
        - GET /api/accounts/me/

    Passwords and internal authentication fields are intentionally omitted.
    """
    is_onboarded = serializers.SerializerMethodField()
    inferred_role = serializers.SerializerMethodField()
    is_department_admin = serializers.SerializerMethodField()
    is_staff = serializers.BooleanField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id", 
            "email",
            "first_name",
            "last_name",
            "role",
            "person",
            "profile",
            "is_onboarded",
            "inferred_role",
            "is_department_admin",
            "is_staff",
            "is_superuser",
        )        
        read_only_fields = fields

    def get_is_onboarded(self, obj) -> bool:
        return obj.person_id is not None

    def get_inferred_role(self, obj) -> str:
        return str(ProfileService.infer_role_from_email(obj.email))

    def get_is_department_admin(self, obj) -> bool:
        if not obj or not obj.person_id:
            return False
        from organization.models import DepartmentAdmin
        return DepartmentAdmin.objects.filter(faculty_id=obj.person_id, is_active=True).exists()

    def get_profile(self, obj):
        """The details of the Person record this account is linked to.

        `person` above is only the id, which tells a client nothing it can
        display -- an account page had no way to show which department or
        roll number the account actually belongs to without fetching every
        user and guessing which one was the current one. This returns the
        real linked record instead, read-only, with the subtype-specific
        fields included only when the person genuinely is that subtype.

        Returns None for an account that has not completed onboarding, so
        a client can tell "no profile" apart from "empty profile".
        """
        person = getattr(obj, "person", None)
        if person is None:
            return None

        data = {
            "full_name": person.full_name,
            "email": person.email or "",
            "department": person.department.name if person.department_id else None,
            "kind": "person",
        }

        student = getattr(person, "student", None)
        if student is not None:
            data["kind"] = "student"
            data["roll_number"] = student.roll_number
            data["academic_level"] = student.academic_level
            return data

        faculty = getattr(person, "faculty", None)
        if faculty is not None:
            data["kind"] = "faculty"
            data["title"] = faculty.title or ""
            data["designation"] = faculty.designation or ""
            data["research_group"] = (
                faculty.research_group.name if faculty.research_group_id else None
            )
            return data

        return data
        

class GoogleLoginSerializer(serializers.Serializer):
    """
    Serializer for Google OAuth login requests.

    The frontend authenticates the user with Google Identity Services and
    sends the resulting Google ID token to the backend. The backend then
    verifies the token with Google before issuing the application's own
    JWT access and refresh tokens.

    Fields:
        id_token: Google-issued ID token (JWT).
    """
    id_token = serializers.CharField(required = True,
                                     allow_blank=True,
                                     trim_whitespace=True)


class StudentOnboardingSerializer(serializers.Serializer):
    """
    Serializer for student onboarding profile completion.
    """
    full_name = serializers.CharField(max_length=255)
    academic_level = serializers.ChoiceField(choices=Student.ACADEMIC_LEVELS)
    roll_number = serializers.CharField(max_length=30, required=False, allow_blank=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)



class FacultyOnboardingSerializer(serializers.Serializer):
    """
    Serializer for faculty onboarding profile completion.
    """
    full_name = serializers.CharField(max_length=255)
    title = serializers.CharField(max_length=50, required=False, allow_blank=True)
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True)
    department_id = serializers.IntegerField(required=False, allow_null=True)
    research_group_id = serializers.IntegerField(required=False, allow_null=True)