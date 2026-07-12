from rest_framework import serializers
from django.contrib.auth import get_user_model


User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer representing the authenticated user.

    Returned by:
        - POST /api/accounts/google/
        - GET /api/accounts/me/

    Passwords and internal authentication fields are intentionally omitted.
    """
  
    class Meta:
        model = User
        fields = (
            "id", 
            "email",
            "first_name",
            "last_name",
            "role",
        )        
        read_only_fields = fields
        

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