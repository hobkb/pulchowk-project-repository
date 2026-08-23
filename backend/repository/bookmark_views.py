from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.views import APIView

from core.responses import success_response
from repository.models import Bookmark, Project
from repository.serializers import ProjectListSerializer


class BookmarkListCreateAPIView(APIView):
    """
    The signed-in user's saved projects.

    The Bookmark model already existed but had no endpoints, so the
    navigation entry for it could only ever have been decorative. Scoped to
    request.user throughout: a user can neither read nor modify anyone
    else's saved projects.
    """

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        bookmarks = (
            Bookmark.objects.filter(user=request.user)
            .select_related("project", "project__department")
            .prefetch_related(
                "project__project_people__person",
                "project__project_keywords__keyword",
                "project__project_domains__domain",
            )
            .order_by("-created_at")
        )
        # A project that has since been unpublished should drop out of the
        # list rather than 404 when opened.
        projects = [b.project for b in bookmarks if b.project.status == "Published"]
        return success_response(
            data=ProjectListSerializer(
                projects, many=True, context={"request": request}
            ).data,
            message="Saved projects retrieved successfully.",
        )

    def post(self, request):
        project_id = request.data.get("project")
        project = get_object_or_404(Project, id=project_id, status="Published")
        _, created = Bookmark.objects.get_or_create(user=request.user, project=project)
        return success_response(
            data={"project": project.id, "bookmarked": True},
            message="Project saved." if created else "Project was already saved.",
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class BookmarkDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, project_id):
        exists = Bookmark.objects.filter(
            user=request.user, project_id=project_id
        ).exists()
        return success_response(data={"project": project_id, "bookmarked": exists})

    def delete(self, request, project_id):
        Bookmark.objects.filter(user=request.user, project_id=project_id).delete()
        return success_response(
            data={"project": project_id, "bookmarked": False},
            message="Project removed from saved projects.",
        )
