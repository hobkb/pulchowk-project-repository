from django.contrib.auth.base_user import  BaseUserManager

class UserManager(BaseUserManager):
     
    """
        Custom manager for the project's email-based User model.

        This manager replaces Django's default UserManager because the project
        authenticates users using their email address instead of a username
        (`USERNAME_FIELD = "email"`).

        Responsibilities:
        - Create regular users with an email and hashed password.
        - Create superusers with the required administrative flags.
        - Normalize email addresses before saving them to improve consistency.
        - Retrieve users using the model's natural key (email), which Django
        uses internally during authentication and management commands.

        Google OAuth users are also created through this manager, ensuring that
        all user creation follows a single, consistent code path regardless of
        whether the account originates from Google authentication or Django's
        `createsuperuser` command.
    """
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        # all new signups automatically store email as lowercased-doman
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, password, **extra_fields)   
    
    def get_by_natural_key(self, username):
       
        return self.get(email__iexact=username)