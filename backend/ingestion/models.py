
from django.db import models
from django.conf import settings


class IngestionJob(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        EXTRACTED = "EXTRACTED", "Extracted"
        DUPLICATE = "DUPLICATE", "Duplicate"
        FAILED = "FAILED", "Failed"
        VERIFIED = "VERIFIED", "Verified"


    file = models.FileField(upload_to="ingestion_pdfs/")
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ingestion_jobs"
    )
    # later use it for classroom uploads
    # classroom_id = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    status = models.CharField(
        max_length=30,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True
    )
    file_hash = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    extracted_payload = models.JSONField(default=dict, blank=True)
    published_project = models.ForeignKey(
        "repository.Project",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ingestion_jobs"
    )
    error_message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ingestion_jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"IngestionJob({self.id}, status={self.status})"


class IngestionJobLog(models.Model):
   
    job = models.ForeignKey(
        IngestionJob,
        on_delete=models.CASCADE,
        related_name="logs"
    )
    level = models.CharField(max_length=20, default="INFO")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ingestion_job_logs"
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.level}] {self.message[:50]}"
