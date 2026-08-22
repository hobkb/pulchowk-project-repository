from django.urls import path
from . import views

app_name = "acocunts_apis"
urlpatterns = [

    path("google/login/", views.GoogleLoginView.as_view(), name='login'),
    path("faculty/", views.FacultyListView.as_view(), name='faculty_list'),
    path("faculty/create/", views.FacultyCreateView.as_view(), name='faculty_create'),
    path("students/", views.StudentListView.as_view(), name='student_list'),
    path("profile/complete/", views.CompleteProfileView.as_view(), name='complete_profile'),
    path("logout/", views.LogoutAPIView.as_view(), name='logout'),
    path("token/refresh/", views.RefreshTokenAPIView.as_view(), name='token_refresh'),
    path("me/", views.CurrentUserView.as_view(), name='fetch_user'),
]