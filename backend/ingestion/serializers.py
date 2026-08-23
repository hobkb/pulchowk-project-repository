from django.conf import settings
from rest_framework import serializers

from repository.models import Project
from ingestion.models import IngestionJob, IngestionJobLog


class IngestionJobCreateSerializer(serializers.ModelSerializer):

    # classroom_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    class Meta:
        model = IngestionJob
        fields = [ "file",
                  #"classroom_id"
                ]

    def validate_file(self, value):
        if not value.name.lower().endswith(".pdf"):
            raise serializers.ValidationError("Only PDF files are allowed.")
        max_mb = getattr(settings, "INGESTION_MAX_UPLOAD_MB", 100)
        if value.size > max_mb * 1024 * 1024:
            raise serializers.ValidationError(f"File size exceeds maximum allowed size of {max_mb} MB.")
        return value


class IngestionJobReadSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email", read_only=True)

    class Meta:
        model = IngestionJob
        fields = [
            "id",
            "file",
            "original_filename",
            "uploaded_by",
            "uploaded_by_email",
           # "classroom_id",

            "status",
            "file_hash",
            "extracted_payload",
            "published_project",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

class ProjectFieldsSerializer(serializers.Serializer):
    title = serializers.CharField(required=False, allow_blank=True)
    abstract = serializers.CharField(required=False, allow_blank=True)
    description = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    project_type = serializers.CharField(required=False, allow_blank=True)
    academic_level = serializers.CharField(required=False, allow_blank=True)
    batch = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    repository_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    github_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    doi_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    publication_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    demo_url = serializers.URLField(
        required=False,
        allow_blank=True,
        allow_null=True,
    )
    language = serializers.CharField(required=False, allow_blank=True)
    department_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    campus_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    research_group_name = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    supervisors = serializers.ListField(required=False, allow_empty=True, allow_null=True)
    # Validated against the same fixed vocabulary the model uses, so an
    # arbitrary value cannot reach the database through the review payload.
    cluster = serializers.ChoiceField(
        choices=[c[0] for c in Project.CLUSTERS],
        required=False,
        allow_blank=True,
        allow_null=True,
    )


class ProjectSectionSerializer(serializers.Serializer):
    display_order = serializers.IntegerField()
    heading = serializers.CharField(required=False)
    canonical_section = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
    )
    heading_level = serializers.IntegerField(required=False)
    content = serializers.CharField(required=False, allow_blank=True)
    page_start = serializers.IntegerField(required=False, allow_null=True)
    page_end = serializers.IntegerField(required=False, allow_null=True)
    word_count = serializers.IntegerField(required=False)
    children = serializers.ListField(
        child=serializers.DictField(),
        required=False,
        allow_empty=True,
    )


class PersonRoleSerializer(serializers.Serializer):
    full_name = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True, allow_null=True)
    roll_number = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    role = serializers.CharField(required=False, allow_blank=True)
    display_order = serializers.IntegerField(required=False, allow_null=True)
    academic_level = serializers.CharField(required=False, allow_blank=True)
    designation = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class IngestionJobUpdatePayloadSerializer(serializers.Serializer):
    project_fields = ProjectFieldsSerializer(required=False)
    project_sections = ProjectSectionSerializer(
        many=True,
        required=False,
    )
    people_and_roles = serializers.ListField(
        child=PersonRoleSerializer(),
        required=False,
        allow_empty=True,
    )
    keywords = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        allow_empty=True,
    )
    references = serializers.ListField(
        child=serializers.DictField(required=False),
        required=False,
        allow_empty=True,
    )
    appendices = serializers.ListField(
        child=serializers.DictField(required=False),
        required=False,
        allow_empty=True,
    )
    document_metadata = serializers.DictField(required=False, allow_empty=True)
    processing_warnings = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        allow_empty=True,
    )

class IngestionJobLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionJobLog
        fields = [
            "level",
            "message",
            "created_at",
        ]
        read_only_fields = fields

