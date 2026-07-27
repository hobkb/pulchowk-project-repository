from django.conf import settings
from rest_framework import serializers
from ingestion.models import IngestionJob, IngestionJobLog


class IngestionJobCreateSerializer(serializers.ModelSerializer):
<<<<<<< Updated upstream
    classroom_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = IngestionJob
        fields = ["id", "file", "classroom_id"]
=======
    # classroom_id = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    class Meta:
        model = IngestionJob
        fields = [ "file",
                  #"classroom_id"
                ]
>>>>>>> Stashed changes

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
<<<<<<< Updated upstream
            "classroom_id",
=======
           # "classroom_id",
>>>>>>> Stashed changes
            "status",
            "file_hash",
            "extracted_payload",
            "published_project",
            "error_message",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class IngestionJobUpdatePayloadSerializer(serializers.Serializer):
    extracted_payload = serializers.JSONField(required=True)


class IngestionJobLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = IngestionJobLog
<<<<<<< Updated upstream
        fields = ["id", "level", "message", "created_at"]
=======
        fields = ["level", "message", "created_at"]
>>>>>>> Stashed changes
        read_only_fields = fields
