from django.urls import path

from .admin_views import (
    AccessRequestDecisionView,
    AccessRequestQueueView,
    MyAccessRequestsView,
    ProjectAccessRequestCancelView,
    ProjectAccessRequestCreateView,
    ProjectManageView,
)
from .bookmark_views import BookmarkDetailAPIView, BookmarkListCreateAPIView
from .similarity_views import SimilarProjectsView, SimilarWorkCheckView
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
    # Semantically similar projects, replacing the same-department listing.
    path(
        "projects/<int:project_id>/similar/",
        SimilarProjectsView.as_view(),
        name="project-similar",
    ),
    # Compare a proposed project against the repository.
    path(
        "similarity-check/",
        SimilarWorkCheckView.as_view(),
        name="similarity-check",
    ),
    # Report access requests.
    path(
        "projects/<int:project_id>/access-request/",
        ProjectAccessRequestCreateView.as_view(),
        name="access-request-create",
    ),
    path(
        "projects/<int:project_id>/access-request/cancel/",
        ProjectAccessRequestCancelView.as_view(),
        name="access-request-cancel",
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
