from google.auth.transport import requests
from google.oauth2 import id_token

from django.conf import settings
from django.db import models, transaction

from .models import User, Person, Student, Faculty, UserRole
from ingestion.pipeline.utils.text_cleaners import normalize_person_name


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
            print(f"GOOGLE OAUTH TOKEN VERIFICATION ERROR: {exc}")
            raise GoogleAuthenticationError(f"Google authentication failed: {exc}") from exc


        if not payload.get("email_verified"):
            raise GoogleAuthenticationError(
                "Google email address is not verified."
            )

        email = payload.get("email", "").lower()

        if not (email.endswith("@pcampus.edu.np") or email.endswith("@ioe.edu.np") or email.endswith(".edu.np")):
            raise GoogleAuthenticationError(
                "Only institutional (.edu.np) Google accounts are allowed."
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
        (`sub`) or email, or creates a new one.
        """
        email = profile["email"]
        sub = profile["sub"]

        user = User.objects.filter(google_sub=sub).first()
        if not user:
            user = User.objects.filter(email=email).first()

        if user:
            user.google_sub = sub
            user.email = email
            user.first_name = profile["first_name"]
            user.last_name = profile["last_name"]
            user.save(update_fields=["google_sub", "email", "first_name", "last_name"])
        else:
            user = User.objects.create(
                google_sub=sub,
                email=email,
                first_name=profile["first_name"],
                last_name=profile["last_name"],
            )
            user.set_unusable_password()
            user.save(update_fields=["password"])

        return user


class ProfileService:
    """
    Service responsible for handling user onboarding, role inference,
    prefill data fetching, and saving Student/Faculty profiles.
    """

    @staticmethod
    def infer_role_from_email(email: str) -> str:
        """
        Determines whether the email belongs to a Student or Faculty.
        Student emails start with roll/batch digits (e.g. 080bct077.sarthak@pcampus.edu.np).
        Faculty emails start with letters (e.g. ram.shrestha@pcampus.edu.np).
        """
        username = email.split("@")[0] if email else ""
        if username and username[0].isdigit():
            return UserRole.STUDENT
        return UserRole.FACULTY

    @staticmethod
    def extract_roll_number_from_email(email: str) -> str:
        """
        Extracts student roll number from email (e.g. 080bct077.sarthak@pcampus.edu.np -> 080BCT077).
        """
        username = email.split("@")[0] if email else ""
        roll = username.split(".")[0] if "." in username else username
        return roll.upper()

    @staticmethod
    def get_prefill_data(user: User) -> dict:
        """
        Fetches any existing prefill data for the user from PDF ingestion or past records.
        """
        email = user.email
        role = ProfileService.infer_role_from_email(email)
        google_full_name = f"{user.first_name} {user.last_name}".strip()

        if role == UserRole.STUDENT:
            # Student lookup: strictly by email
            student = Student.objects.filter(email=email).first()
            extracted_roll = ProfileService.extract_roll_number_from_email(email)
            if student:
                return {
                    "full_name": student.full_name,
                    "department_id": student.department_id,
                    "academic_level": student.academic_level,
                    "roll_number": student.roll_number or extracted_roll,
                }
            return {
                "full_name": google_full_name,
                "roll_number": extracted_roll,
            }
        else:
            # Faculty lookup: check by email first, fallback to full_name (case-insensitive)
            faculty = Faculty.objects.filter(
                models.Q(email=email) | models.Q(full_name__iexact=google_full_name)
            ).first()

            if faculty:
                return {
                    "full_name": faculty.full_name,
                    "department_id": faculty.department_id,
                    "title": faculty.title,
                    "designation": faculty.designation,
                    "research_group_id": faculty.research_group_id,
                }

        # Default fallback from Google SSO payload
        return {
            "full_name": google_full_name,
        }

    @staticmethod
    @transaction.atomic
    def save_student_profile(user: User, data: dict) -> Student:
        """
        Updates an existing student record (matched strictly by email) or creates a new one.
        Roll number is strictly derived from the verified institutional email address.
        """
        email = user.email
        derived_roll = ProfileService.extract_roll_number_from_email(email)
        existing_student = Student.objects.filter(email=email).first()
        full_name = normalize_person_name(data["full_name"])

        if existing_student:
            existing_student.full_name = full_name
            existing_student.academic_level = data["academic_level"]
            existing_student.roll_number = derived_roll
            if data.get("department_id"):
                existing_student.department_id = data["department_id"]
            existing_student.save()
            student = existing_student
        else:
            student = Student.objects.create(
                email=email,
                full_name=full_name,
                academic_level=data["academic_level"],
                roll_number=derived_roll,
                department_id=data.get("department_id"),
            )
        return student


    @staticmethod
    @transaction.atomic
    def save_faculty_profile(user: User, data: dict) -> Faculty:
        """
        Updates an existing faculty record (matched by email or full_name) or creates a new one.
        """
        email = user.email
        full_name = normalize_person_name(data["full_name"].strip())

        existing_faculty = Faculty.objects.filter(
            models.Q(email=email) | models.Q(full_name__iexact=full_name)
        ).first()

        if existing_faculty:
            existing_faculty.email = email
            existing_faculty.full_name = full_name
            existing_faculty.title = data.get("title", existing_faculty.title)
            existing_faculty.designation = data.get("designation", existing_faculty.designation)
            if data.get("department_id"):
                existing_faculty.department_id = data["department_id"]
            if data.get("research_group_id"):
                existing_faculty.research_group_id = data["research_group_id"]
            existing_faculty.save()
            faculty = existing_faculty
        else:
            faculty = Faculty.objects.create(
                email=email,
                full_name=full_name,
                title=data.get("title", ""),
                designation=data.get("designation", ""),
                department_id=data.get("department_id"),
                research_group_id=data.get("research_group_id"),
            )
        return faculty



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