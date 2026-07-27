from rest_framework.views import APIView
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from ingestion.models import IngestionJob, IngestionJobLog
from ingestion.serializers import (
    IngestionJobCreateSerializer,
    IngestionJobReadSerializer,
    IngestionJobUpdatePayloadSerializer,
    IngestionJobLogSerializer,
)
from ingestion.tasks import run_ingestion_pipeline
from repository.models import Project, ProjectSection

from core.responses import success_response

class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def get_job_for_user(job_id, user):
    try:
        if user.is_staff:
            return IngestionJob.objects.get(id=job_id)

        return IngestionJob.objects.get(
            id=job_id,
            uploaded_by=user,
        )

    except IngestionJob.DoesNotExist:
        raise NotFound("Job not found.")


class JobListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = IngestionJobCreateSerializer(data=request.data)

        if not serializer.is_valid():
            raise ValidationError(serializer.errors)

        uploaded_file = serializer.validated_data["file"]
       # classroom_id = serializer.validated_data.get("classroom_id")

        job = IngestionJob.objects.create(
            file=uploaded_file,
            original_filename=uploaded_file.name,
            uploaded_by=request.user,
           # classroom_id=classroom_id,
            status=IngestionJob.Status.PENDING,
        )

        IngestionJobLog.objects.create(
            job=job,
            level="INFO",
            message=(
                f"Job created by {request.user.email}. "
                f"File: {uploaded_file.name}"
            ),
        )

        run_ingestion_pipeline.delay(str(job.id))

        return success_response(
            data=IngestionJobReadSerializer(job).data,
            message="Job created successfully.",
            status=status.HTTP_201_CREATED,
        )

    def get(self, request):
        queryset = (
            IngestionJob.objects.all()
            if request.user.is_staff
            else IngestionJob.objects.filter(uploaded_by=request.user)
        )

        job_status = request.query_params.get("status")
        if job_status:
            queryset = queryset.filter(status=job_status)

       # classroom_id = request.query_params.get("classroom_id")
       # if classroom_id:
       #     queryset = queryset.filter(classroom_id=classroom_id)

        paginator = StandardResultsSetPagination()

        page = paginator.paginate_queryset(
            queryset,
            request,
        )

        if page is not None:
            serializer = IngestionJobReadSerializer(
                page,
                many=True,
            )

            return paginator.get_paginated_response(serializer.data)

        serializer = IngestionJobReadSerializer(
            queryset,
            many=True,
        )

        return success_response(
            data=serializer.data,
            message="Jobs retrieved successfully.",
        )

class JobDetailAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]

    def get(self, request, job_id):
        job = get_job_for_user(job_id, request.user)

        serializer = IngestionJobReadSerializer(job)

        return success_response(
            data=serializer.data,
            message="Job retrieved successfully.",
        )

    def patch(self, request, job_id):
        job = get_job_for_user(job_id, request.user)

        if job.status != IngestionJob.Status.EXTRACTED:
            raise ValidationError(
                {
                    "detail": (
                        "Cannot edit payload unless job status is "
                        f"EXTRACTED. Current status: {job.status}"
                    )
                }
            )

        serializer = IngestionJobUpdatePayloadSerializer(
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)

        payload = job.extracted_payload or {}

        # Update project fields
        if "project_fields" in serializer.validated_data:
            payload.setdefault("project_fields", {})
            payload["project_fields"].update(
                serializer.validated_data["project_fields"]
            )

        # Update project sections
        if "project_sections" in serializer.validated_data:
            payload.setdefault("project_sections", [])

            existing = {
                section["display_order"]: section
                for section in payload["project_sections"]
            }

            for updated_section in serializer.validated_data["project_sections"]:
                order = updated_section["display_order"]

                if order in existing:
                    existing[order].update(updated_section)
                else:
                    payload["project_sections"].append(updated_section)

        job.extracted_payload = payload
        job.save(
            update_fields=[
                "extracted_payload",
                "updated_at",
            ]
        )

        IngestionJobLog.objects.create(
            job=job,
            level="INFO",
            message=(
                f"Draft metadata updated by "
                f"{request.user.email}."
            ),
        )

        return success_response(
            data=IngestionJobReadSerializer(job).data,
            message="Metadata updated successfully.",
        )
        
class JobLogsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, job_id):
        job = get_job_for_user(job_id, request.user)

        logs = job.logs.all().order_by("created_at")

        serializer = IngestionJobLogSerializer(
            logs,
            many=True,
        )

        return success_response(
            data=serializer.data,
            message="Job logs retrieved successfully.",
        )
        
class JobPublishAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, job_id):
        job = get_job_for_user(job_id, request.user)
        
        if job.published_project is not None:
            raise ValidationError(
                {
                    "detail": (
                        "This job has already been published."
                    )
                }
            )
        if job.status != IngestionJob.Status.EXTRACTED:
            raise ValidationError(
                {
                    "detail": (
                        "Job can only be published when status is "
                        f"EXTRACTED. Current status: {job.status}"
                    )
                }
            )

        payload = job.extracted_payload or {}
        project_fields = payload.get("project_fields", {})

        title = (
            project_fields.get("title")
            or job.original_filename
            or "Untitled Project"
        )

        abstract = project_fields.get("abstract") or ""

        project_type = (
            project_fields.get("project_type")
            if project_fields.get("project_type")
            in [choice[0] for choice in Project.PROJECT_TYPES]
            else "Major"
        )

        academic_level = (
            project_fields.get("academic_level")
            if project_fields.get("academic_level")
            in [choice[0] for choice in Project.ACADEMIC_LEVELS]
            else "UG"
        )

        batch = project_fields.get("batch")
        github_url = project_fields.get("repository_url")

        project = Project.objects.create(
            title=title,
            abstract=abstract,
            project_type=project_type,
            academic_level=academic_level,
            batch=batch,
            github_url=github_url,
            status="Ready",
            created_by=request.user,
        )

        raw_sections = payload.get("project_sections", [])

        for idx, sec in enumerate(raw_sections):
            ProjectSection.objects.create(
                project=project,
                heading=sec.get(
                    "heading",
                    f"Section {idx + 1}",
                ),
                canonical_section=sec.get("canonical_section"),
                heading_level=sec.get("heading_level", 1),
                display_order=sec.get(
                    "display_order",
                    idx + 1,
                ),
                content=sec.get("content", ""),
                page_start=sec.get("page_start"),
                page_end=sec.get("page_end"),
                word_count=sec.get("word_count", 0),
            )

        job.published_project = project
        job.status = IngestionJob.Status.VERIFIED

        job.save(
            update_fields=[
                "published_project",
                "status",
                "updated_at",
            ]
        )

        IngestionJobLog.objects.create(
            job=job,
            level="INFO",
            message=(
                f"Job published to repository.Project "
                f"({project.id}) by user "
                f"{request.user.email}. "
                "Status set to VERIFIED."
            ),
        )

        return success_response(
            data={
                "project_id": str(project.id),
            },
            message="Project published successfully.",
            status=status.HTTP_200_OK,
        )