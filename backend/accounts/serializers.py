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

    class Meta:
        model = User
        fields = (
            "id", 
            "email",
            "first_name",
            "last_name",
            "role",
            "person",
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