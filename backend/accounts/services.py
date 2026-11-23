from google.auth.transport import requests
from google.oauth2 import id_token

from django.conf import settings
from django.db import models, transaction

from .models import User, Person, Student, Faculty, UserRole
from ingestion.pipeline.utils.text_cleaners import (
    ROLL_PATTERN,
    clean_roll_number,
    normalize_person_name,
)


class GoogleAuthenticationError(Exception):
    """Raised when Google authentication fails."""


class ProfileConflict(Exception):
    """
    Raised when a profile cannot be saved because the identity it claims
    belongs to an existing record. Surfaced to the client as a 400 with an
    explanation, rather than reaching the database and becoming an opaque
    "duplicate key" 500.
    """


class GoogleService:
    """Verifies Google ID tokens against Google's public endpoint.

    Checks signature and audience, requires a verified email, and restricts
    authentication to the campus domain.
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
            print("GOOGLE TOKEN ERROR:", repr(exc))
            raise GoogleAuthenticationError(f"Google token verification failed: {exc}") from exc

        if not payload.get("email_verified"):
            raise GoogleAuthenticationError(
                "Google email address is not verified."
            )

        email = payload.get("email", "").lower()

        # `settings` is already imported at module level; re-importing it
        # here would make the name local to this whole function and break
        # the settings.GOOGLE_CLIENT_ID use above with an UnboundLocalError.
        allowed = getattr(settings, "ALLOWED_LOGIN_DOMAINS", ("pcampus.edu.np",))
        if not any(email.endswith(f"@{domain}") for domain in allowed):
            raise GoogleAuthenticationError(
                "Authentication failed. Please sign in with your Pulchowk Campus Google Account."
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
    def verified_roll_number(email: str):
        """
        The roll number proven by the institutional address, or None.

        Addresses are issued by the campus, so a roll number in the local
        part is evidence. Anything typed into the form is not -- which is
        why this is the only source allowed to claim an existing record.
        """
        candidate = clean_roll_number(
            ProfileService.extract_roll_number_from_email(email)
        )
        return candidate if ROLL_PATTERN.fullmatch(candidate or "") else None

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
        Links the signed-in user to their Student record.

        Publishing a project already creates Student rows from roll numbers
        read out of the PDF, so the record this person needs usually exists
        before they ever sign in. Adopting it is the right outcome -- but
        only when the roll number came from the verified campus address.
        A typed roll number is an assertion, not proof, so it may create a
        record but never take over one that already exists.
        """
        email = user.email
        verified_roll = ProfileService.verified_roll_number(email)
        typed_roll = clean_roll_number(str(data.get("roll_number") or "").strip())
        roll = verified_roll or typed_roll

        if not roll:
            raise ProfileConflict(
                "A roll number is required. Enter the roll number printed on "
                "your registration record."
            )

        existing = Student.objects.filter(email=email).first()
        by_roll = Student.objects.filter(roll_number=roll).first()

        if by_roll is not None and by_roll != existing:
            if verified_roll:
                # Their own address carries this roll number, so the record
                # extracted from their report is theirs to take over.
                existing = by_roll
            else:
                raise ProfileConflict(
                    f"Roll number {roll} is already registered to another "
                    "account. If this is yours, contact your department "
                    "administrator."
                )

        # A Person row holding this address that is not a student cannot be
        # converted into one -- Person/Student is a table-per-type split.
        clash = Person.objects.filter(email=email)
        if existing is not None:
            clash = clash.exclude(pk=existing.pk)
        if clash.exists():
            raise ProfileConflict(
                "This email address is already recorded against a different "
                "person in the repository. Contact your department "
                "administrator to have the records merged."
            )

        full_name = normalize_person_name(data["full_name"])

        if existing is not None:
            existing.full_name = full_name
            existing.email = email
            existing.academic_level = data["academic_level"]
            existing.roll_number = roll
            if data.get("department_id"):
                existing.department_id = data["department_id"]
            existing.save()
            return existing

        return Student.objects.create(
            email=email,
            full_name=full_name,
            academic_level=data["academic_level"],
            roll_number=roll,
            department_id=data.get("department_id"),
        )


    @staticmethod
    @transaction.atomic
    def save_faculty_profile(user: User, data: dict) -> Faculty:
        """Link the signed-in user to their Faculty record.

        Matched on the verified email address and nothing else. The previous
        lookup also matched full name and honoured a client-supplied
        `faculty_id`, so typing a supervisor's name handed over that
        supervisor's record and every project attributed to them. A name is
        not a credential.

        An unmatched address creates a new record. A resulting duplicate is
        merged by an administrator; a wrong merge is far cheaper to undo than
        a wrongly claimed identity.
        """
        email = user.email
        full_name = normalize_person_name(data["full_name"].strip())

        existing = Faculty.objects.filter(email=email).first()

        clash = Person.objects.filter(email=email)
        if existing is not None:
            clash = clash.exclude(pk=existing.pk)
        if clash.exists():
            raise ProfileConflict(
                "This email address is already recorded against a different "
                "person in the repository. Contact your department "
                "administrator to have the records merged."
            )

        if existing is not None:
            existing.full_name = full_name
            existing.title = data.get("title", existing.title)
            existing.designation = data.get("designation", existing.designation)
            if data.get("department_id"):
                existing.department_id = data["department_id"]
            if data.get("research_group_id"):
                existing.research_group_id = data["research_group_id"]
            existing.save()
            return existing

        return Faculty.objects.create(
            email=email,
            full_name=full_name,
            title=data.get("title", ""),
            designation=data.get("designation", ""),
            department_id=data.get("department_id"),
            research_group_id=data.get("research_group_id"),
        )
