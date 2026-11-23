from django.urls import path

from .views import (
    NotificationClearAllAPIView,
    NotificationListAPIView,
    NotificationMarkAllReadAPIView,
    NotificationMarkReadAPIView,
    NotificationUnreadCountAPIView,
)

app_name = "notifications"

urlpatterns = [
    path("", NotificationListAPIView.as_view(), name="notification-list"),
    path("read-all/", NotificationMarkAllReadAPIView.as_view(), name="notification-mark-all-read"),
    path("clear-all/", NotificationClearAllAPIView.as_view(), name="notification-clear-all"),
    path("unread-count/", NotificationUnreadCountAPIView.as_view(), name="notification-unread-count"),
    path("<int:notification_id>/read/", NotificationMarkReadAPIView.as_view(), name="notification-mark-read"),
]
