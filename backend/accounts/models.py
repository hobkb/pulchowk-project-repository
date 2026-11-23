import uuid
from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from .managers import UserManager
from organization.models import Department, ResearchGroup
from ingestion.pipeline.utils.text_cleaners import normalize_person_name

class UserRole(models.TextChoices):
    STUDENT = "student", "Student"
    FACULTY = "faculty", "Faculty"
    ADMIN = "admin", "Admin"
    EXTERNAL = "external", "External"


# this model will be changed and not have email 
class User(AbstractUser):
    username = None

    email = models.EmailField(unique=True)

    person = models.OneToOneField(
        'Person',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_account"
    )
    is_onboarded = models.BooleanField(default=False)
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

    full_name = models.CharField(max_length=255)

    email = models.EmailField(
        unique=True,
        null=True,
        blank=True,
    )

    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )

    class Meta:
        db_table="persons"

    def save(self, *args, **kwargs):
        if self.full_name:
            self.full_name = normalize_person_name(self.full_name)
        super().save(*args, **kwargs)
        
    def __str__(self):
            return self.full_name
    
    
class Student(Person):
    
    ACADEMIC_LEVELS = [
            ("UG", "UG"),
            ("Masters", "Masters"),
            ("PhD", "PhD"),
        ]
   
    academic_level = models.CharField(max_length=20, choices=ACADEMIC_LEVELS)
    roll_number = models.CharField(
        max_length=30,
        unique=True,
    )
    
class Faculty(Person):

    title = models.CharField(
        max_length=50,
        blank=True,
    )
        
    designation = models.CharField(
        max_length=100,
        blank=True,
    )
    # if faculty belong to many then this can be ManyToManyField
    research_group = models.ForeignKey(ResearchGroup, 
                                       null=True,
                                       blank=True,
                                       on_delete=models.SET_NULL)
    

class External(Person):

    organization = models.CharField(
        max_length=255,
        blank=True
    )

    designation = models.CharField(
        max_length=100,
        blank=True
    )


class RoleElevationRequest(models.Model):
    """
    A request to hold a privileged role (faculty or admin).

    Onboarding must not grant these on the applicant's own say-so: both
    carry `is_staff`, which makes someone a reviewer -- able to publish,
    delete projects and decide report-access requests -- and admin also
    carries `is_superuser`. So the role is asked for here and granted only
    when an existing administrator approves it.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        DECLINED = "DECLINED", "Declined"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="role_requests",
    )
    requested_role = models.CharField(max_length=20, choices=UserRole.choices)
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_role_requests",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "role_elevation_requests"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="PENDING"),
                name="unique_pending_role_request",
            )
        ]

    def __str__(self):
        return f"RoleElevationRequest({self.user_id} -> {self.requested_role}, {self.status})"
