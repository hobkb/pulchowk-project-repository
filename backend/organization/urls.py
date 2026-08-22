from django.urls import path
from .views import CampusListView, DepartmentListView, ResearchGroupListView

app_name = "organization"

urlpatterns = [
    path("campuses/", CampusListView.as_view(), name="campus-list"),
    path("departments/", DepartmentListView.as_view(), name="department-list"),
    path("research-groups/", ResearchGroupListView.as_view(), name="researchgroup-list"),
]
