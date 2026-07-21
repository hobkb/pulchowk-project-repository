import uuid
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


class Person(models.Model):
    ACADEMIC_LEVELS = [
        ("UG", "UG"),
        ("Masters", "Masters"),
        ("PhD", "PhD"),
        ("Faculty", "Faculty"),
        ("External", "External"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, blank=True, null=True)
    academic_level = models.CharField(max_length=20, choices=ACADEMIC_LEVELS)
    identifier = models.CharField(max_length=100, blank=True, null=True)
    designation = models.CharField(max_length=150, blank=True, null=True)
    is_claimed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "persons"

    def __str__(self):
        return self.full_name