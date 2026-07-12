from django.urls import path
from . import views

app_name = "acocunts_apis"
urlpatterns = [

    path("google/login/", views.GoogleLoginView.as_view(), name='login'),
    path("logout/", views.LogoutAPIView.as_view(), name='logout'),
    path("token/refresh/", views.RefreshTokenAPIView.as_view(), name='token_refresh'),
    path("me/", views.CurrentUserView.as_view(), name='fetch_user'),
  
]