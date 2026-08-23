from rest_framework import serializers

from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    """
    Read-only -- notifications are created only by services.py, never via
    the API. Mirrors the read-only pattern already used by
    accounts.serializers.UserSerializer.
    """

    class Meta:
        model = Notification
        fields = (
            "id",
            "notification_type",
            "message",
            "job",
            "project",
            "is_read",
            "created_at",
        )
        read_only_fields = fields
