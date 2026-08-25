
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.conf import settings
from pgvector.django import HnswIndex, VectorField
from organization.models import Department, ResearchGroup
from ingestion.pipeline.utils.text_cleaners import normalize_canonical_section, normalize_person_name, normalize_section_title

class Project(models.Model):
    # The department's research clusters. A fixed, validated vocabulary --
    # kept as choices on the project rather than as free-text Domain rows,
    # because only these seven values are ever valid and the API must be
    # able to reject anything else.
    CLUSTERS = [
        ("AIML", "AIML"),
        ("ANLP", "ANLP"),
        ("NTS", "NTS"),
        ("EII", "EII"),
        ("EDMES", "EDMES"),
        ("ACOM", "ACOM"),
        ("IPCV", "IPCV"),
    ]

    PROJECT_TYPES = [
        ("Major", "Major"),
        ("Minor", "Minor"),
        ("Thesis", "Thesis"),
        ("Faculty Project", "Faculty Project"),
        ("Research", "Research"),
    ]
    # The value is what is stored and filtered on; the label is what a
    # reader sees. Nothing in the interface should show a bare code.
    ACADEMIC_LEVELS = [
        ("UG", "Undergraduate"),
        ("Masters", "Masters"),
        ("PhD", "Doctor of Philosophy"),
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
    # Nullable so every project that predates this field stays valid; the
    # migration adds it without touching existing rows.
    cluster = models.CharField(
        max_length=10, choices=CLUSTERS, blank=True, null=True, db_index=True
    )
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="Processing")
    language = models.CharField(max_length=50, default="English")
    thumbnail = models.ImageField(upload_to="thumbnails/",blank=True,null=True,)
    github_url = models.URLField(blank=True, null=True)
    doi_url = models.URLField(blank=True, null=True)
    publication_url = models.URLField(blank=True, null=True)
    demo_url = models.URLField(blank=True, null=True)
    submitted_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="projects", null=True, blank=True)
    research_group = models.ForeignKey(ResearchGroup, on_delete=models.SET_NULL, null=True, blank=True, related_name="projects")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_projects")
    extraction_verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="verified_projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Weighted full-text index over the catalogue metadata: title, keywords,
    # abstract, department and the names of the people credited. Maintained by
    # repository.search_index; see that module for why the previous chained
    # icontains search had to be replaced.
    search_vector = SearchVectorField(null=True, editable=False)

    class Meta:
        db_table = "projects"
        indexes = [
            GinIndex(fields=["search_vector"], name="project_search_vector_gin"),
        ]

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


class ProjectEmbedding(models.Model):
    """One semantic vector for one project under one embedding model.

    Kept in its own table rather than as a column on Project for three
    reasons. A model migration can write the new vectors alongside the old
    ones and only then switch over, so search is never served from a
    half-rebuilt index. The freshness bookkeeping (which model, which source
    text, generated when) stays out of the project row that the catalogue
    reads on every request. And when section-level embeddings are added for
    retrieval-augmented answering later, they become a sibling table rather
    than a second set of columns here.

    `source_hash` is the digest of the exact text that was embedded. An
    embedding is stale when that digest no longer matches the text the
    current representation would produce, which makes regeneration a pure
    function of content rather than a guess about which fields changed.
    """

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="embeddings"
    )
    model_version = models.CharField(max_length=64, db_index=True)
    source_hash = models.CharField(max_length=64)
    embedding = VectorField(dimensions=384)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_embeddings"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "model_version"],
                name="uniq_project_embedding_per_model",
            )
        ]
        indexes = [
            # Cosine distance, because the vectors are stored L2-normalised
            # and similarity is what every caller wants. At the present corpus
            # size Postgres will sequentially scan regardless; the index costs
            # almost nothing to carry and is what keeps the query plan stable
            # as the repository grows.
            HnswIndex(
                name="project_embedding_hnsw",
                fields=["embedding"],
                m=16,
                ef_construction=64,
                opclasses=["vector_cosine_ops"],
            )
        ]

    def __str__(self):
        return f"{self.project_id}@{self.model_version}"


class SimilarityCalibration(models.Model):
    """Where a raw cosine sits in this corpus.

    Cosine has no absolute meaning here. Every project is an undergraduate
    engineering report from one department written in a similar house style,
    so two unrelated projects still score a median of about 0.64 and reach
    0.82 at the ninety-ninth percentile. Telling a reader "0.79" is therefore
    close to meaningless; telling them the score is higher than 97% of
    arbitrary pairs in this repository is not.

    `breakpoints` is the random-pair distribution measured by
    `manage.py search_eval`, stored as ascending [percentile, cosine] pairs.
    One row per embedding model, because the distribution belongs to the
    model as much as to the corpus.

    `corpus_size` is recorded so a calibration measured on 95 projects is
    visibly a calibration measured on 95 projects once there are a thousand.
    """

    model_version = models.CharField(max_length=64, unique=True)
    corpus_size = models.IntegerField()
    pair_count = models.IntegerField()
    sampled = models.BooleanField(default=False)
    breakpoints = models.JSONField(default=list)
    generated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "similarity_calibration"

    def __str__(self):
        return f"{self.model_version} @ {self.corpus_size} projects"

    def percentile_for(self, score):
        """Percentile of `score` within the measured random-pair distribution.

        Linear interpolation between breakpoints; clamped at both ends, so a
        score below everything measured reads as the lowest stored percentile
        rather than as zero, and one above everything reads as the highest.
        Returns None when no calibration has been recorded.
        """
        points = self.breakpoints or []
        if not points:
            return None
        if score <= points[0][1]:
            return float(points[0][0])
        if score >= points[-1][1]:
            return float(points[-1][0])
        for (p_low, c_low), (p_high, c_high) in zip(points, points[1:]):
            if c_low <= score <= c_high:
                if c_high == c_low:
                    return float(p_high)
                ratio = (score - c_low) / (c_high - c_low)
                return round(float(p_low) + ratio * (float(p_high) - float(p_low)), 1)
        return float(points[-1][0])


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

    def save(self, *args, **kwargs):
        if self.heading:
            self.heading = normalize_section_title(self.heading)
        if self.canonical_section:
            self.canonical_section = normalize_canonical_section(self.canonical_section)
        super().save(*args, **kwargs)


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


class ProjectAccessRequest(models.Model):
    """
    A reader asking the department for the full report of one project.

    Handled entirely inside the application rather than by email: an
    approval has to actually unlock the PDF for that reader, which a mail
    thread cannot do, and the requester sees the decision the moment it is
    made through the existing notification system.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        DECLINED = "DECLINED", "Declined"

    project = models.ForeignKey(
        Project, on_delete=models.CASCADE, related_name="access_requests"
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="project_access_requests",
    )
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="decided_access_requests",
    )
    decision_note = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "project_access_requests"
        ordering = ["-created_at"]
        constraints = [
            # One live request per person per project: re-asking while a
            # request is still open would just spam the reviewers, and
            # re-asking after approval is pointless.
            models.UniqueConstraint(
                fields=["project", "requester"],
                condition=models.Q(status__in=["PENDING", "APPROVED"]),
                name="unique_open_project_access_request",
            )
        ]

    def __str__(self):
        return f"AccessRequest({self.id}, project={self.project_id}, {self.status})"

    @property
    def is_granted(self):
        return self.status == self.Status.APPROVED
