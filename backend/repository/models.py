import uuid
from django.db import models
from django.conf import settings


class Campus(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    location = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "campuses"

    def __str__(self):
        return self.name


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campus = models.ForeignKey(Campus, on_delete=models.CASCADE, related_name="departments")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "departments"
        unique_together = ("campus", "code")

    def __str__(self):
        return f"{self.name} ({self.code})"


class ResearchGroup(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="research_groups")
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "research_groups"

    def __str__(self):
        return self.name


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
        ("Ready", "Ready"),
        ("Archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.TextField()
    abstract = models.TextField()
    description = models.TextField(blank=True, null=True)
    project_type = models.CharField(max_length=30, choices=PROJECT_TYPES)
    academic_level = models.CharField(max_length=20, choices=ACADEMIC_LEVELS)
    batch = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Processing")
    language = models.CharField(max_length=50, default="English")
    thumbnail_url = models.TextField(blank=True, null=True)
    github_url = models.TextField(blank=True, null=True)
    doi_url = models.TextField(blank=True, null=True)
    publication_url = models.TextField(blank=True, null=True)
    demo_url = models.TextField(blank=True, null=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="projects", null=True, blank=True)
    research_group = models.ForeignKey(ResearchGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_projects")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="approved_projects")
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="assets")
    asset_type = models.CharField(max_length=30, choices=ASSET_TYPES)
    file_name = models.CharField(max_length=255)
    storage_path = models.TextField()
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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_people")
    person = models.ForeignKey("accounts.Person", on_delete=models.CASCADE, related_name="project_people", null=True, blank=True)
    role = models.CharField(max_length=30, choices=ROLE_CHOICES)
    display_order = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_people"
        ordering = ["display_order"]


class ProjectSection(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="sections")
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


class Keyword(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        db_table = "keywords"


class ProjectKeyword(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_keywords")
    keyword = models.ForeignKey(Keyword, on_delete=models.CASCADE, related_name="project_keywords")

    class Meta:
        db_table = "project_keywords"
        unique_together = ("project", "keyword")


class Domain(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "domains"


class ProjectDomain(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="project_domains")
    domain = models.ForeignKey(Domain, on_delete=models.CASCADE, related_name="project_domains")

    class Meta:
        db_table = "project_domains"
        unique_together = ("project", "domain")


class Bookmark(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="bookmarks")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="bookmarks")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bookmarks"
        unique_together = ("user", "project")
