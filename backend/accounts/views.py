from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db import transaction

from .models import User, UserRole, Faculty, Student, RoleElevationRequest
from .serializers import (
    GoogleLoginSerializer,
    UserSerializer,
    StudentOnboardingSerializer,
    FacultyOnboardingSerializer,
    FacultySerializer,
    FacultyCreateSerializer,
    StudentSerializer,
)
from .services import (
    GoogleService,
    GoogleAuthenticationError,
    UserService,
    ProfileService,
)
from core.responses import success_response
from notifications.services import NotificationService

from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.exceptions import AuthenticationFailed

from django.conf import settings

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
class GoogleLoginView(APIView):
    
    """
    Authenticates users using a Google ID token.

    Upon successful verification, the user is created or retrieved,
    JWT access and refresh tokens are issued as HttpOnly cookies,
    and the authenticated user's profile is returned along with
    inferred role and prefill data for onboarding.
    """
    authentication_classes = []
    permission_classes = [AllowAny]

    
    def post(self, request):
        serializer= GoogleLoginSerializer(data= request.data)
        serializer.is_valid(raise_exception=True)
        
        
        try:
            profile = GoogleService.verify_id_token(token = serializer.validated_data.get("id_token"))
       
        except GoogleAuthenticationError as exc:
          raise AuthenticationFailed(str(exc))
        
        user = UserService.get_or_create_google_user(profile)
        
        refresh = RefreshToken.for_user(user=user)
        access  = refresh.access_token
        
        inferred_role = ProfileService.infer_role_from_email(user.email)
        prefill_data = ProfileService.get_prefill_data(user)
        
        user_data = UserSerializer(user).data
        user_data["inferred_role"] = inferred_role
        user_data["prefill_data"] = prefill_data
        
        response = success_response(
            data=user_data,
            message="Login successful.",
        )
                
        response.set_cookie(
            key="refresh",
            value = str(refresh),
            httponly=True,
            secure = not settings.DEBUG,
            samesite="Lax"
        )
        
        response.set_cookie(
            key="access",
            value = str(access),
            httponly=True,
            secure = not settings.DEBUG,
            samesite="Lax"
        )
        
        return response


class CompleteProfileView(APIView):
    """
    Saves or updates the user's Student or Faculty profile details during onboarding.

    Infers role based on email format (Student if starts with digits, Faculty otherwise).
    Matches existing Student records by email, or Faculty records by email/full_name.
    """
    permission_classes = [IsAuthenticated]

    # Roles that carry real power and therefore cannot be self-assigned.
    # `is_staff` alone makes someone a reviewer -- able to publish, delete
    # projects and decide report-access requests -- so faculty is gated too,
    # not just admin.
    PRIVILEGED_ROLES = {UserRole.FACULTY, UserRole.ADMIN}

    @transaction.atomic
    def post(self, request):
        user = request.user

        # The role is chosen during onboarding. The email-shape guess is
        # only the default the form starts on, because it cannot tell a
        # faculty member from an administrator, and a campus address whose
        # local part happens to start with a letter is not evidence of
        # anything on its own.
        requested = str(request.data.get("role") or "").strip().lower()
        if requested in {UserRole.STUDENT, UserRole.FACULTY, UserRole.ADMIN}:
            role = requested
        else:
            role = ProfileService.infer_role_from_email(user.email)

        if role == UserRole.STUDENT:
            serializer = StudentOnboardingSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            person = ProfileService.save_student_profile(user, serializer.validated_data)
        else:
            serializer = FacultyOnboardingSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            person = ProfileService.save_faculty_profile(user, serializer.validated_data)

        user.person = person

        pending_role = None
        if role in self.PRIVILEGED_ROLES:
            # The profile is saved, but the privilege is not granted here.
            # The account starts as a student and an existing administrator
            # decides whether to elevate it.
            pending_role = role
            user.role = UserRole.STUDENT
            user.is_staff = False
            user.is_superuser = False
        else:
            user.role = UserRole.STUDENT
            user.is_staff = False
            user.is_superuser = False

        user.save(update_fields=["person", "role", "is_staff", "is_superuser"])

        if pending_role:
            elevation, created = RoleElevationRequest.objects.get_or_create(
                user=user,
                status=RoleElevationRequest.Status.PENDING,
                defaults={
                    "requested_role": pending_role,
                    "reason": str(request.data.get("role_reason") or "").strip()[:2000],
                },
            )
            if created:
                NotificationService.notify_role_requested(elevation)

        data = UserSerializer(user).data
        data["pending_role"] = pending_role
        return success_response(
            data=data,
            message=(
                "Profile saved. Your request for "
                f"{pending_role} access is awaiting approval from an administrator."
                if pending_role
                else "Profile saved successfully."
            ),
        )


class FacultyListView(APIView):
    """
    Returns a list of extracted / existing faculty members for selection during onboarding.
    """
    permission_classes = [AllowAny]

    def get(self, request):
        faculties = Faculty.objects.all().order_by("full_name")
        serializer = FacultySerializer(faculties, many=True)
        return success_response(data=serializer.data)


class CurrentUserView(APIView):
        
    """
    Returns the profile of the currently authenticated user.

    Requires a valid access token.
    """
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
       
        return success_response(
            data=UserSerializer(request.user).data,
        )
    

class RefreshTokenAPIView(APIView):
    
    
    """
    Refreshes the access token using the refresh token stored in
    the HttpOnly cookie.

    Authentication is intentionally disabled because the access
    token may have already expired.
    """
    
    authentication_classes = []
    permission_classes = [AllowAny]
    def post(self, request):

        refresh_token = request.COOKIES.get("refresh")

        if not refresh_token:
            raise AuthenticationFailed("No Refresh Token")

        # built-in serializer handles getting new refresh and access tokens  and blacklisting old one
        serializer = TokenRefreshSerializer(
            data={"refresh": refresh_token}
        )

        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as exc:
            # An expired/invalid/malformed refresh token raises a bare
            # TokenError, which is not a DRF exception and would otherwise
            # crash this endpoint with an uncaught 500 instead of a clean
            # authentication failure the frontend can act on.
            raise AuthenticationFailed(str(exc)) from exc
        
        access_token = serializer.validated_data["access"]
        # Present only when ROTATE_REFRESH_TOKENS=True 
        new_refresh_token = serializer.validated_data.get("refresh")  
       
        response = success_response(message="Token Refreshed.")

        response.set_cookie(
            key="access",
            value=access_token,
            httponly=True,
            secure=False,
            samesite="Lax"
        )
        
        if new_refresh_token is not None:
              response.set_cookie(
                key="refresh",
                value=new_refresh_token,
                httponly=True,
                secure=False,
                samesite="Lax"
            )
            
        return response


class LogoutAPIView(APIView):
    
    """
    Logs the user out by blacklisting the refresh token (if present)
    and removing the authentication cookies.

    Authentication is intentionally disabled so logout succeeds even
    when the access token has expired.
    """
    authentication_classes = []
    permission_classes = [AllowAny]
    
    def post(self, request):
            
        refresh_token = request.COOKIES.get("refresh")
        
        if refresh_token:
            
            try:
                 # Security check performed here 
                 token = RefreshToken(refresh_token)
                 token.blacklist()
            except:
                pass

        response = success_response(message="Logged Out Successfully!")
        response.delete_cookie("access")
        response.delete_cookie("refresh")
        
        return response 


class FacultyCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = FacultyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        faculty = serializer.save()
        return success_response(
            data=FacultySerializer(faculty).data,
            message="Faculty created successfully.",
        )


class StudentListView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        from django.db import models
        roll_number = request.query_params.get("roll_number")
        q = request.query_params.get("q")
        queryset = Student.objects.all()

        if roll_number:
            from ingestion.pipeline.utils.text_cleaners import clean_roll_number
            cleaned_roll = clean_roll_number(roll_number)
            queryset = queryset.filter(roll_number__iexact=cleaned_roll)
        elif q:
            queryset = queryset.filter(
                models.Q(full_name__icontains=q) | models.Q(roll_number__icontains=q)
            )

        students = queryset[:20]
        serializer = StudentSerializer(students, many=True)
        return success_response(data=serializer.data)