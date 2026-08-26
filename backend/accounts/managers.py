from django.contrib.auth.base_user import  BaseUserManager

class UserManager(BaseUserManager):
     
    """Manager for the email-based User model (`USERNAME_FIELD = "email"`).

    Google OAuth accounts are created through this manager too, so all user
    creation follows one code path regardless of origin.
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