from django.urls import path

from .admin_views import (
    AccessRequestDecisionView,
    AccessRequestQueueView,
    MyAccessRequestsView,
    ProjectAccessRequestCreateView,
    ProjectManageView,
)
from .bookmark_views import BookmarkDetailAPIView, BookmarkListCreateAPIView
from .views import (
    ProjectChoicesView,
    ProjectDetailView,
    ProjectFacetsView,
    ProjectListView,
)


app_name = "repository"

urlpatterns = [
    path("projects/", ProjectListView.as_view(), name="project-list"),
    path("projects/choices/", ProjectChoicesView.as_view(), name="project-choices"),
    path("projects/facets/", ProjectFacetsView.as_view(), name="project-facets"),
    path("projects/<int:project_id>/", ProjectDetailView.as_view(), name="project-detail"),
    # Reviewer-only edit / delete for a published record.
    path("projects/<int:project_id>/manage/", ProjectManageView.as_view(), name="project-manage"),
    # Report access requests.
    path(
        "projects/<int:project_id>/access-request/",
        ProjectAccessRequestCreateView.as_view(),
        name="access-request-create",
    ),
    path("access-requests/mine/", MyAccessRequestsView.as_view(), name="access-request-mine"),
    path("access-requests/", AccessRequestQueueView.as_view(), name="access-request-queue"),
    path(
        "access-requests/<int:request_id>/<str:decision>/",
        AccessRequestDecisionView.as_view(),
        name="access-request-decision",
    ),
    path("bookmarks/", BookmarkListCreateAPIView.as_view(), name="bookmark-list-create"),
    path("bookmarks/<int:project_id>/", BookmarkDetailAPIView.as_view(), name="bookmark-detail"),
]
