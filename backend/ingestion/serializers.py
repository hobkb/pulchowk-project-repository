from django.conf import settings
from rest_framework import serializers
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
        max_mb = getattr(settings, "INGESTION_MAX_UPLOAD_MB", 25)
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
    title = serializers.CharField(required=False)
    abstract = serializers.CharField(required=False, allow_blank=True)
    project_type = serializers.CharField(required=False)
    academic_level = serializers.CharField(required=False)
    batch = serializers.IntegerField(required=False, allow_null=True)
    repository_url = serializers.URLField(
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



class IngestionJobUpdatePayloadSerializer(serializers.Serializer):
    project_fields = ProjectFieldsSerializer(required=False)
    project_sections = ProjectSectionSerializer(
        many=True,
        required=False,
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


