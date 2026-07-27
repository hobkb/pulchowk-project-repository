from django.urls import path

from .views import JobDetailAPIView, JobListCreateAPIView, JobLogsAPIView, JobPublishAPIView


app_name = "ingestion"

urlpatterns = [

    path("jobs/", JobListCreateAPIView.as_view(), name="job-list-create"),
    path("jobs/<int:job_id>/", JobDetailAPIView.as_view(), name="job-detail"),
    path("jobs/<int:job_id>/logs/", JobLogsAPIView.as_view(), name="job-logs"),
    path("jobs/<int:job_id>/publish/", JobPublishAPIView.as_view(), name="job-publish"),

]
