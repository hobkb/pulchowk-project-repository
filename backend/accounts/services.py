from google.auth.transport import requests
from google.oauth2 import id_token

from django.conf import settings
from django.db import transaction

from .models import User


class GoogleAuthenticationError(Exception):
    """Raised when Google authentication fails."""


class GoogleService:
    """
    Service responsible for verifying Google ID tokens.

    This service communicates with Google's public authentication endpoint
    to validate the ID token received from the frontend.

    Responsibilities:
        - Verify token signature.
        - Verify token audience.
        - Ensure the email is verified.
        - Restrict authentication to @pcampus.edu.np accounts.
        - Return normalized user information.
    """
  
    @staticmethod
    def verify_id_token(token: str) -> dict:
        try:
            payload = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID,
            )
        except Exception as exc:
            raise GoogleAuthenticationError("Invalid Google token.") from exc

        if not payload.get("email_verified"):
            raise GoogleAuthenticationError(
                "Google email address is not verified."
            )

        email = payload.get("email", "").lower()

        if not email.endswith("@pcampus.edu.np"):
            raise GoogleAuthenticationError(
                "Only Pulchowk Campus Google accounts are allowed."
            )

        return {
            "sub": payload["sub"],
            "email": email,
            "first_name": payload.get("given_name", ""),
            "last_name": payload.get("family_name", ""),
        }


class UserService:
    """
    Service responsible for creating and updating application users.

    Google is treated as the source of truth for identity information.
    """

    @staticmethod
    @transaction.atomic
    def get_or_create_google_user(profile: dict) -> User:
        """
        Finds an existing user using Google's stable subject identifier
        (`sub`) or creates a new one.

        Existing users have their profile information synchronized with
        Google's latest data. 
        """

        user, created = User.objects.get_or_create(
            google_sub=profile["sub"],
            defaults={
                "email": profile["email"],
                "first_name": profile["first_name"],
                "last_name": profile["last_name"],
            },
        )
        # To synchronize with google's latest data the existing info will be updated with fetched profile
        if not created:
            user.email = profile["email"]
            user.first_name = profile["first_name"]
            user.last_name = profile["last_name"]
         
            user.save(
                update_fields=[
                    "email",
                    "first_name",
                    "last_name",
                         ]
            )
        else:
            # Google-only login account
            user.set_unusable_password()
            user.save(update_fields=["password"])

        return user