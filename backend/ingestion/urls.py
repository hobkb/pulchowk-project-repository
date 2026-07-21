from django.urls import path
from ingestion import views

app_name = "ingestion"

urlpatterns = [
    path("jobs/", views.job_list_create_view, name="job-list-create"),
    path("jobs/<uuid:job_id>/", views.job_detail_view, name="job-detail"),
    path("jobs/<uuid:job_id>/logs/", views.job_logs_view, name="job-logs"),
    path("jobs/<uuid:job_id>/publish/", views.job_publish_view, name="job-publish"),
]
