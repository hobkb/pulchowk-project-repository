from django.urls import path
<<<<<<< Updated upstream
from ingestion import views
=======
from .views import JobDetailAPIView, JobListCreateAPIView, JobLogsAPIView, JobPublishAPIView
>>>>>>> Stashed changes

app_name = "ingestion"

urlpatterns = [
<<<<<<< Updated upstream
    path("jobs/", views.job_list_create_view, name="job-list-create"),
    path("jobs/<uuid:job_id>/", views.job_detail_view, name="job-detail"),
    path("jobs/<uuid:job_id>/logs/", views.job_logs_view, name="job-logs"),
    path("jobs/<uuid:job_id>/publish/", views.job_publish_view, name="job-publish"),
=======
    path("jobs/", JobListCreateAPIView.as_view(), name="job-list-create"),
    path("jobs/<int:job_id>/", JobDetailAPIView.as_view(), name="job-detail"),
    path("jobs/<int:job_id>/logs/", JobLogsAPIView.as_view(), name="job-logs"),
    path("jobs/<int:job_id>/publish/", JobPublishAPIView.as_view(), name="job-publish"),
>>>>>>> Stashed changes
]
