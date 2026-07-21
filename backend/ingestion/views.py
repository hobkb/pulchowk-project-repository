from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from ingestion.models import IngestionJob, IngestionJobLog
from ingestion.serializers import (
    IngestionJobCreateSerializer,
    IngestionJobReadSerializer,
    IngestionJobUpdatePayloadSerializer,
    IngestionJobLogSerializer,
)
from ingestion.tasks import run_ingestion_pipeline
from repository.models import Project, ProjectSection


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def get_job_for_user(job_id, user):
    try:
        if user.is_staff:
            return IngestionJob.objects.get(id=job_id)
        return IngestionJob.objects.get(id=job_id, uploaded_by=user)
    except IngestionJob.DoesNotExist:
        return None


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def job_list_create_view(request):
    if request.method == "POST":
        serializer = IngestionJobCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        uploaded_file = serializer.validated_data["file"]
        classroom_id = serializer.validated_data.get("classroom_id")

        job = IngestionJob.objects.create(
            file=uploaded_file,
            original_filename=uploaded_file.name,
            uploaded_by=request.user,
            classroom_id=classroom_id,
            status=IngestionJob.Status.PENDING,
        )

        IngestionJobLog.objects.create(
            job=job,
            level="INFO",
            message=f"Job created by {request.user.email}. File: {uploaded_file.name}"
        )

        # Enqueue Celery background task
        run_ingestion_pipeline.delay(str(job.id))

        read_serializer = IngestionJobReadSerializer(job)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)

    elif request.method == "GET":
        queryset = IngestionJob.objects.all() if request.user.is_staff else IngestionJob.objects.filter(uploaded_by=request.user)

        job_status = request.query_params.get("status")
        if job_status:
            queryset = queryset.filter(status=job_status)

        classroom_id = request.query_params.get("classroom_id")
        if classroom_id:
            queryset = queryset.filter(classroom_id=classroom_id)

        paginator = StandardResultsSetPagination()
        page = paginator.paginate_queryset(queryset, request)
        if page is not None:
            serializer = IngestionJobReadSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = IngestionJobReadSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["GET", "PATCH"])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([JSONParser])
def job_detail_view(request, job_id):
    job = get_job_for_user(job_id, request.user)
    if not job:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        serializer = IngestionJobReadSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == "PATCH":
        if job.status != IngestionJob.Status.EXTRACTED:
            return Response(
                {"detail": f"Cannot edit payload unless job status is EXTRACTED. Current status: {job.status}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = IngestionJobUpdatePayloadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        job.extracted_payload = serializer.validated_data["extracted_payload"]
        job.save(update_fields=["extracted_payload", "updated_at"])

        IngestionJobLog.objects.create(
            job=job,
            level="INFO",
            message=f"Draft metadata payload manually updated by user {request.user.email}."
        )

        read_serializer = IngestionJobReadSerializer(job)
        return Response(read_serializer.data, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def job_logs_view(request, job_id):
    job = get_job_for_user(job_id, request.user)
    if not job:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    logs = job.logs.all().order_by("created_at")
    serializer = IngestionJobLogSerializer(logs, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([permissions.IsAuthenticated])
def job_publish_view(request, job_id):
    job = get_job_for_user(job_id, request.user)
    if not job:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)

    if job.status != IngestionJob.Status.EXTRACTED:
        return Response(
            {"detail": f"Job can only be published when status is EXTRACTED. Current status: {job.status}"},
            status=status.HTTP_400_BAD_REQUEST
        )

    payload = job.extracted_payload or {}
    project_fields = payload.get("project_fields", {})

    title = project_fields.get("title") or job.original_filename or "Untitled Project"
    abstract = project_fields.get("abstract") or ""
    project_type = project_fields.get("project_type") if project_fields.get("project_type") in [t[0] for t in Project.PROJECT_TYPES] else "Major"
    academic_level = project_fields.get("academic_level") if project_fields.get("academic_level") in [l[0] for l in Project.ACADEMIC_LEVELS] else "UG"
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

    # Populate project sections
    raw_sections = payload.get("project_sections", [])
    for idx, sec in enumerate(raw_sections):
        ProjectSection.objects.create(
            project=project,
            heading=sec.get("heading", f"Section {idx+1}"),
            canonical_section=sec.get("canonical_section"),
            heading_level=sec.get("heading_level", 1),
            display_order=sec.get("display_order", idx + 1),
            content=sec.get("content", ""),
            page_start=sec.get("page_start"),
            page_end=sec.get("page_end"),
            word_count=sec.get("word_count", 0),
        )

    job.published_project = project
    job.status = IngestionJob.Status.VERIFIED
    job.save(update_fields=["published_project", "status", "updated_at"])

    IngestionJobLog.objects.create(
        job=job,
        level="INFO",
        message=f"Job published to repository.Project ({project.id}) by user {request.user.email}. Status set to VERIFIED."
    )

    return Response({"project_id": str(project.id)}, status=status.HTTP_200_OK)
