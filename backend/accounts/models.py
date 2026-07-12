from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UserManager

class UserRole(models.TextChoices):
    STUDENT = "student", "Student"
    FACULTY = "faculty", "Faculty"
    ADMIN = "admin", "Admin"


class User(AbstractUser):
    username = None

    email = models.EmailField(unique=True)

    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
    )

    google_sub = models.CharField(
        max_length=255,
        unique=True,
     
        blank=True,
        null=True,
    )
    objects = UserManager()
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email