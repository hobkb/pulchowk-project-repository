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
        return f"{self.name} ({self.code})"


class ResearchGroup(models.Model):
   
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="research_groups")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    
    class Meta:
        db_table = "research_groups"

    def __str__(self):
        return self.name
