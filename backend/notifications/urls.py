from django.urls import path

from .views import (
    NotificationListAPIView,
    NotificationMarkAllReadAPIView,
    NotificationMarkReadAPIView,
    NotificationUnreadCountAPIView,
)

app_name = "notifications"

urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="notification-list"),
    path("read-all/", NotificationMarkAllReadAPIView.as_view(), name="notification-mark-all-read"),
    path("unread-count/", NotificationUnreadCountAPIView.as_view(), name="notification-unread-count"),
    path("<int:notification_id>/read/", NotificationMarkReadAPIView.as_view(), name="notification-mark-read"),
]
