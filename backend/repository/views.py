from django.db.models import Q
from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from core.responses import success_response
from repository.models import Project
from repository.serializers import ProjectDetailSerializer, ProjectListSerializer


def get_published_project_queryset():
    return (
        Project.objects.filter(status="Published")
        .select_related("department", "research_group")
        .prefetch_related(
            "project_people__person",
            "sections",
            "project_keywords__keyword",
            "project_domains__domain",
            "references",
            "assets",
        )
    )


class ProjectListView(APIView):
    """
    Public read-only list of verified (Published) projects.
    Supports text search ('q'), department filtering, academic level / major filtering, and project_type (Minor/Major) filtering.
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = get_published_project_queryset()

        search = (request.query_params.get("q") or "").strip()
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search)
                | Q(abstract__icontains=search)
                | Q(description__icontains=search)
                | Q(project_people__person__full_name__icontains=search)
                | Q(project_keywords__keyword__name__icontains=search)
                | Q(project_type__icontains=search)
                | Q(academic_level__icontains=search)
                | Q(batch__icontains=search)
            ).distinct()

        department = (request.query_params.get("department") or "").strip()
        if department and department.lower() != "all":
            if department.isdigit():
                queryset = queryset.filter(department_id=int(department))
            else:
                queryset = queryset.filter(department__name__icontains=department).distinct()

        academic_level = (request.query_params.get("academic_level") or request.query_params.get("major") or "").strip()
        if academic_level and academic_level.lower() != "all":
            queryset = queryset.filter(academic_level__iexact=academic_level)

        project_type = (request.query_params.get("project_type") or "").strip()
        if project_type and project_type.lower() != "all":
            queryset = queryset.filter(project_type__iexact=project_type)

        projects = list(queryset)
        serializer = ProjectListSerializer(
            projects,
            many=True,
            context={"request": request},
        )

        return success_response(
            data=serializer.data,
            message="Projects retrieved successfully.",
        )


class ProjectDetailView(APIView):
    """Public read-only detail view for a single verified project."""

    permission_classes = [permissions.AllowAny]

    def get(self, request, project_id):
        project = get_published_project_queryset().filter(id=project_id).first()
        if project is None:
            raise NotFound("Project not found.")

        serializer = ProjectDetailSerializer(
            project,
            context={"request": request},
        )

        return success_response(
            data=serializer.data,
            message="Project retrieved successfully.",
        )


class ProjectChoicesView(APIView):
    """
    Public endpoint exposing backend-defined choices and batch constraints.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        from datetime import datetime
        academic_levels = [
            {"value": choice[0], "label": choice[1]}
            for choice in Project.ACADEMIC_LEVELS
        ]
        project_types = [
            {"value": choice[0], "label": choice[1]}
            for choice in Project.PROJECT_TYPES
        ]

        now = datetime.now()
        current_bs_year = now.year + (57 if now.month >= 4 else 56)
        max_batch_num = current_bs_year - 2001

        min_batch = 65
        batch_options = [f"{b:03d}" for b in range(min_batch, max_batch_num + 1)]

        data = {
            "academic_levels": academic_levels,
            "project_types": project_types,
            "batch": {
                "min": f"{min_batch:03d}",
                "max": f"{max_batch_num:03d}",
                "options": batch_options,
            },
        }

        return success_response(
            data=data,
            message="Project metadata choices retrieved successfully.",
        )