from django.urls import path

from .views import ProjectDetailView, ProjectListView


app_name = "repository"

urlpatterns = [
    path("projects/", ProjectListView.as_view(), name="project-list"),
    path("projects/<int:project_id>/", ProjectDetailView.as_view(), name="project-detail"),
]