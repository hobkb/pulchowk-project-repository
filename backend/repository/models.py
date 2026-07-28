
from django.db import models
from django.conf import settings
from organization.models import Department, ResearchGroup

class Project(models.Model):
    PROJECT_TYPES = [
        ("Major", "Major"),
        ("Minor", "Minor"),
        ("Thesis", "Thesis"),
        ("Faculty Project", "Faculty Project"),
        ("Research", "Research"),
    ]
    ACADEMIC_LEVELS = [
        ("UG", "UG"),
        ("Masters", "Masters"),
        ("PhD", "PhD"),
        ("Faculty", "Faculty"),
    ]
    STATUS_CHOICES = [
        ("Processing", "Processing"),
        ("Review Required", "Review Required"),
        ("Published", "Published"),
        ("Archived", "Archived"),
    ]

    
    title = models.TextField()
    abstract = models.TextField()
    description = models.TextField(blank=True, null=True)
    project_type = models.CharField(max_length=30, choices=PROJECT_TYPES)
    academic_level = models.CharField(max_length=20, choices=ACADEMIC_LEVELS)
    batch = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Processing")
    language = models.CharField(max_length=50, default="English")
    thumbnail = models.ImageField(upload_to="thumbnails/",blank=True,null=True,)
    github_url = models.URLField(blank=True)
    doi_url = models.URLField(blank=True)
    publication_url = models.URLField(blank=True)
    demo_url = models.URLField(blank=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="projects")
    research_group = models.ForeignKey(ResearchGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_projects")
    extraction_verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "projects"

    def __str__(self):
        return self.title[:50]


class ProjectAsset(models.Model):
    ASSET_TYPES = [
        ("Report", "Report"),
        ("Poster", "Poster"),
        ("Presentation", "Presentation"),
        ("Dataset", "Dataset"),
        ("Source Code", "Source Code"),
        ("Supplementary", "Supplementary"),
    ]
  
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assets")
    asset_type = models.CharField(max_length=30, choices=ASSET_TYPES)
    file = models.FileField(upload_to="projects/")
    mime_type = models.CharField(max_length=100)
    file_size = models.BigIntegerField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_assets"


class ProjectPerson(models.Model):
    ROLE_CHOICES = [
        ("Author", "Author"),
        ("Supervisor", "Supervisor"),
        ("Co-Supervisor", "Co-Supervisor"),
        ("Faculty Author", "Faculty Author"),
        ("Industry Mentor", "Industry Mentor"),
    ]
   
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_people")
    person = models.ForeignKey("accounts.Person", on_delete=models.CASCADE, related_name="project_people")
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    display_order = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_people"
        ordering = ["display_order"]
        constraints = [
            models.UniqueConstraint(
                fields=["project", "person", "role"],
                name="unique_project_person_role",
            )
        ]


class ProjectSection(models.Model):

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sections")
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
    )
    heading = models.CharField(max_length=255)
    canonical_section = models.CharField(max_length=100, blank=True, null=True)
    heading_level = models.SmallIntegerField()
    display_order = models.IntegerField()
    content = models.TextField()
    page_start = models.IntegerField(blank=True, null=True)
    page_end = models.IntegerField(blank=True, null=True)
    word_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_sections"
        ordering = ["display_order"]


class ProjectReference(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="references")
    title = models.CharField(max_length=255, blank=True)
    citation = models.TextField(blank=True)
    url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_references"


class Keyword(models.Model):

    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "keywords"


class ProjectKeyword(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_keywords")
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name="project_keywords")

    class Meta:
        db_table = "project_keywords"
        constraints = [
        models.UniqueConstraint(
            fields=["project", "keyword"],
            name="unique_project_keyword",
            )
        ]


class Domain(models.Model):
 
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        db_table = "domains"


class ProjectDomain(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_domains")
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="project_domains")

    class Meta:
        db_table = "project_domains"
        constraints = [
                models.UniqueConstraint(
                    fields=["project", "domain"],
                    name="unique_project_domain",
                    )
                ]


class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bookmarks"
        constraints = [
                models.UniqueConstraint(
                    fields=["project", "user"],
                    name="unique_project_bookmark",
                    )
                ]
