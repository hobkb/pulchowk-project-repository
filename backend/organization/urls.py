from django.urls import path
from .views import DepartmentListView

app_name = "organization"

urlpatterns = [
    path("departments/", DepartmentListView.as_view(), name="department-list"),
]
