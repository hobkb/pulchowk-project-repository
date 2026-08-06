from django.db import models

# Create your models here.

class Campus(models.Model):
    
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=255)
    
    class Meta:
        db_table = "campuses"

    def __str__(self):
        return self.name


class Department(models.Model):

    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=100)

    class Meta:
        db_table = "departments"
    

    def __str__(self):
        return f"{self.name}"


class ResearchGroup(models.Model):
   
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="research_groups")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = "research_groups"

    def __str__(self):
        return self.name


class DepartmentAdmin(models.Model):
    """
    Represents a Faculty member who serves as the Departmental Admin / 
    Head of Project Management for a specific Department.
    """
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="department_admins"
    )
    faculty = models.ForeignKey(
        'accounts.Faculty',
        on_delete=models.CASCADE,
        related_name="admin_roles"
    )
    designation_title = models.CharField(
        max_length=100,
        default="Project Coordinator / Head of Project Management",
        help_text="e.g. Major Project Coordinator 2080"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Designates whether this faculty member currently holds active admin rights."
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "department_admins"
        verbose_name = "Department Admin"
        verbose_name_plural = "Department Admins"
        constraints = [
            models.UniqueConstraint(
                fields=["department", "faculty"],
                condition=models.Q(is_active=True),
                name="unique_active_department_admin"
            )
        ]

    def __str__(self):
        return f"{self.faculty.full_name} ({self.department.name} Admin)"
