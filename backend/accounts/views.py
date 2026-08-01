from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.db import transaction

from .models import UserRole
from .serializers import (
    GoogleLoginSerializer,
    UserSerializer,
    StudentOnboardingSerializer,
    FacultyOnboardingSerializer,
)
from .services import (
    GoogleService,
    GoogleAuthenticationError,
    UserService,
    ProfileService,
)
from core.responses import success_response

from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.exceptions import AuthenticationFailed

from django.conf import settings


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

    @transaction.atomic
    def post(self, request):
        user = request.user
        inferred_role = ProfileService.infer_role_from_email(user.email)

        if inferred_role == UserRole.STUDENT:
            serializer = StudentOnboardingSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            person = ProfileService.save_student_profile(user, serializer.validated_data)
        else:
            serializer = FacultyOnboardingSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            person = ProfileService.save_faculty_profile(user, serializer.validated_data)

        # Link person to user and update role
        user.person = person
        user.role = inferred_role
        user.save(update_fields=["person", "role"])

        return success_response(
            data=UserSerializer(user).data,
            message="Profile saved successfully.",
        )


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
        
        serializer.is_valid(raise_exception=True)
        
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