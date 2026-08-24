from django.shortcuts import get_object_or_404
from rest_framework import permissions
from rest_framework.pagination import PageNumberPagination
from rest_framework.views import APIView

from core.responses import success_response

from .models import Notification
from .serializers import NotificationSerializer


class NotificationPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NotificationListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = request.user.notifications.all()
        paginator = NotificationPagination()
        page = paginator.paginate_queryset(queryset, request)
        serializer = NotificationSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class NotificationMarkReadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, notification_id):
        notification = get_object_or_404(
            Notification, id=notification_id, recipient=request.user
        )
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return success_response(
            data=NotificationSerializer(notification).data,
            message="Notification marked as read.",
        )


class NotificationMarkAllReadAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        updated = request.user.notifications.filter(is_read=False).update(is_read=True)
        return success_response(
            data={"updated": updated},
            message="All notifications marked as read.",
        )


class NotificationClearAllAPIView(APIView):
    """Deletes every notification the signed-in user has, permanently.

    Scoped to request.user throughout -- deleting is a queryset filtered
    by recipient, never a bare Notification.objects.all(), so this can
    only ever remove the requester's own notifications."""

    permission_classes = [permissions.IsAuthenticated]

    def delete(self, request):
        deleted, _ = request.user.notifications.all().delete()
        return success_response(
            data={"deleted": deleted},
            message="Notifications cleared." if deleted else "Nothing to clear.",
        )


class NotificationUnreadCountAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        count = request.user.notifications.filter(is_read=False).count()
        return success_response(data={"count": count})
