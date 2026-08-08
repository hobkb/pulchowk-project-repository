import uuid
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
