from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.views import APIView

from core.responses import paginated_response, success_response
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
        # A project that has since been unpublished drops out of the list
        # rather than 404ing when opened. This has to be a queryset filter,
        # not a list comprehension after the fact, or the page counts would
        # describe rows that were then discarded.
        bookmarks = (
            Bookmark.objects.filter(user=request.user, project__status="Published")
            .select_related("project", "project__department")
            .prefetch_related(
                "project__project_people__person",
                "project__project_keywords__keyword",
                "project__project_domains__domain",
            )
            .order_by("-created_at")
        )
        return paginated_response(
            request,
            bookmarks,
            lambda rows: ProjectListSerializer(
                [b.project for b in rows], many=True, context={"request": request}
            ).data,
            page_size=5,
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
