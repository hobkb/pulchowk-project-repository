from django.db import transaction
from django.utils.text import slugify
from rest_framework.views import APIView
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from accounts.models import Person
from ingestion.models import IngestionJob, IngestionJobLog
from ingestion.serializers import (
    IngestionJobCreateSerializer,
    IngestionJobReadSerializer,
    IngestionJobUpdatePayloadSerializer,
    IngestionJobLogSerializer,
)
from ingestion.tasks import run_ingestion_pipeline
from organization.models import Campus, Department, ResearchGroup
from repository.models import (
    Domain,
    Keyword,
    Project,
    ProjectAsset,
    ProjectDomain,
    ProjectKeyword,
    ProjectPerson,
    ProjectReference,
    ProjectSection,
)

from core.responses import success_response


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def get_job_for_user(job_id, user):
    try:
        # Strictly enforce admin/staff access
        if user.is_staff:
            return IngestionJob.objects.get(id=job_id)

        # Non-staff users are rejected
        raise NotFound("Job not found.")
    
    except IngestionJob.DoesNotExist:
        raise NotFound("Job not found.")


class JobListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated,
                         # permissions.IsAdminUser,  
                          ]
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
    """
    Unified endpoint replacing JobReviewAPIView and JobReviewStatusAPIView.
    Retrieves job details, review completeness status, and updates metadata draft.
    """
    permission_classes = [permissions.IsAuthenticated,
                         # permissions.IsAdminUser,  # Restrict to admins only
                          ]
    parser_classes = [JSONParser]

    def get(self, request, job_id):
        job = get_job_for_user(job_id, request.user)
        payload = job.extracted_payload or {}
    
        # Compute review completeness status directly for the UI
        available_sections = [
            "project_fields",
            "people_and_roles",
            "keywords",
            "project_sections",
            "references",
            "appendices",
            "document_metadata",
            "processing_warnings",
        ]
    
        review_state = {
            section: ("pending" if payload.get(section) in (None, [], {}, "") else "available")
            for section in available_sections
        }
    
        serializer = IngestionJobReadSerializer(job)
        data = serializer.data
        data["review_state"] = review_state
    
        return success_response(
            data=data,
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
    
        if "project_fields" in serializer.validated_data:
            payload.setdefault("project_fields", {})
            payload["project_fields"].update(
                serializer.validated_data["project_fields"]
            )
    
        if "project_sections" in serializer.validated_data:
            payload.setdefault("project_sections", [])
    
            existing = {
                section.get("display_order"): section
                for section in payload["project_sections"]
            }
    
            for updated_section in serializer.validated_data["project_sections"]:
                order = updated_section["display_order"]
    
                if order in existing:
                    existing[order].update(updated_section)
                else:
                    payload["project_sections"].append(updated_section)
    
        for field_name in [
            "people_and_roles",
            "keywords",
            "references",
            "appendices",
            "document_metadata",
            "processing_warnings",
        ]:
            if field_name in serializer.validated_data:
                payload[field_name] = serializer.validated_data[field_name]
    
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
    permission_classes = [permissions.IsAuthenticated,
                         # permissions.IsAdminUser,  # Restrict to admins only
                          ]

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
    permission_classes = [permissions.IsAuthenticated,
                         # permissions.IsAdminUser,  # Restrict to admins only
                          ]
    @staticmethod
    def _iter_sections(sections):
        for section in sections:
            if not isinstance(section, dict):
                continue
            yield section
            yield from JobPublishAPIView._iter_sections(section.get("children") or [])

    @classmethod
    def _create_sections(cls, project, sections, parent=None):
        for index, section_data in enumerate(sections, start=1):
            if not isinstance(section_data, dict):
                continue
            section = ProjectSection.objects.create(
                project=project,
                parent=parent,
                heading=section_data.get("heading", f"Section {index}"),
                canonical_section=section_data.get("canonical_section"),
                heading_level=section_data.get("heading_level", 1),
                display_order=section_data.get("display_order", index),
                content=section_data.get("content", ""),
                page_start=section_data.get("page_start"),
                page_end=section_data.get("page_end"),
                word_count=section_data.get("word_count", 0),
            )
            cls._create_sections(
                project,
                section_data.get("children") or [],
                parent=section,
            )
    def _validate_publish_payload(self, payload):
        project_fields = payload.get("project_fields", {})
        title = (project_fields.get("title") or "").strip()
        abstract = (project_fields.get("abstract") or "").strip()
        people = payload.get("people_and_roles") or []
        keywords = [value for value in (payload.get("keywords") or []) if str(value).strip()]
        sections = payload.get("project_sections") or []
    
        errors = {}
        if not title:
            errors.setdefault("project_fields.title", []).append("Title is required.")
        if not abstract:
            errors.setdefault("project_fields.abstract", []).append("Abstract is required.")
    
        authors = [person for person in people if str(person.get("role") or "").lower() == "author"]
        if not authors:
            errors.setdefault("people_and_roles", []).append("At least one author is required.")
    
        seen_author_names = set()
        duplicate_authors = []
        for person in authors:
            name = str(person.get("full_name") or "").strip().lower()
            if not name:
                continue
            if name in seen_author_names:
                duplicate_authors.append(str(person.get("full_name") or "").strip())
            seen_author_names.add(name)
        if duplicate_authors:
            errors.setdefault("people_and_roles", []).append(
                "Duplicate authors are not allowed: " + ", ".join(sorted(set(duplicate_authors)))
            )
    
        department_name = (project_fields.get("department_name") or "").strip()
        if not department_name:
            errors.setdefault("project_fields.department_name", []).append(
                "Department could not be resolved from the extracted metadata."
            )
    
        if not sections:
            errors.setdefault("project_sections", []).append("At least one section is required.")
    
        for index, section in enumerate(self._iter_sections(sections)):
            heading_level = section.get("heading_level") or 1
            if not isinstance(heading_level, int) or heading_level < 1 or heading_level > 6:
                errors.setdefault("project_sections", []).append(
                    f"Section {index + 1} has an invalid heading level."
                )
                break
            
        if not keywords:
            errors.setdefault("keywords", []).append("At least one keyword is required.")
    
        if errors:
            raise ValidationError(errors)
    
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
        self._validate_publish_payload(payload)
    
        project_fields = payload.get("project_fields", {})
        title = (project_fields.get("title") or job.original_filename or "Untitled Project").strip()
        abstract = (project_fields.get("abstract") or "").strip()
    
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
        github_url = project_fields.get("repository_url") or project_fields.get("github_url")
        department_name = (project_fields.get("department_name") or "").strip()
        campus_name = (project_fields.get("campus_name") or "Unknown Campus").strip()
        research_group_name = (project_fields.get("research_group_name") or "").strip()
    
        with transaction.atomic():
            campus, _ = Campus.objects.get_or_create(
                name=campus_name or "Unknown Campus",
                defaults={"location": "Unknown"},
            )
            department, _ = Department.objects.get_or_create(
                name=department_name or "Unknown Department",
                defaults={"campus": campus},
            )
            if department.campus_id != campus.id:
                department.campus = campus
                department.save(update_fields=["campus"])
    
            research_group = None
            if research_group_name:
                research_group, _ = ResearchGroup.objects.get_or_create(
                    department=department,
                    name=research_group_name,
                    defaults={"description": ""},
                )
    
            project = Project.objects.create(
                title=title,
                abstract=abstract,
                description=project_fields.get("description") or "",
                project_type=project_type,
                academic_level=academic_level,
                batch=batch,
                language=project_fields.get("language") or "English",
                github_url=github_url,
                doi_url=project_fields.get("doi_url") or "",
                publication_url=project_fields.get("publication_url") or "",
                demo_url=project_fields.get("demo_url") or "",
                department=department,
                research_group=research_group,
                status="Published",
                created_by=request.user,
            )
    
            self._create_sections(project, payload.get("project_sections", []))
               
            people = payload.get("people_and_roles") or []
            for person_data in people:
                full_name = str(person_data.get("full_name") or "").strip()
                if not full_name:
                    continue
    
                role = str(person_data.get("role") or "Author").strip() or "Author"
                email = (person_data.get("email") or "").strip()
                if not email:
                    slug = slugify(full_name) or "person"
                    email = f"{slug}@example.invalid"
    
                person, _ = Person.objects.get_or_create(
                    email=email,
                    defaults={
                        "full_name": full_name,
                        "department": department,
                    },
                )
                if person.full_name != full_name or person.department_id != department.id:
                    person.full_name = full_name
                    person.department = department
                    person.save(update_fields=["full_name", "department"])
    
                ProjectPerson.objects.create(
                    project=project,
                    person=person,
                    role=role,
                    display_order=person_data.get("display_order") or 1,
                )
    
            keywords = [value for value in (payload.get("keywords") or []) if str(value).strip()]
            for keyword_name in keywords:
                keyword, _ = Keyword.objects.get_or_create(name=str(keyword_name).strip())
                ProjectKeyword.objects.get_or_create(project=project, keyword=keyword)
    
            domains = []
            for domain_name in payload.get("domains") or []:
                if str(domain_name).strip():
                    domains.append(str(domain_name).strip())
            if not domains and isinstance(project_fields.get("domains"), str):
                domains = [project_fields.get("domains")]
    
            for domain_name in domains:
                domain, _ = Domain.objects.get_or_create(name=domain_name)
                ProjectDomain.objects.get_or_create(project=project, domain=domain)
    
            references = payload.get("references") or []
            for reference in references:
                if not isinstance(reference, dict):
                    continue
                title = str(reference.get("title") or reference.get("name") or "").strip()
                citation = str(reference.get("citation") or reference.get("content") or "").strip()
                url = str(reference.get("url") or "").strip()
                if not title and not citation and not url:
                    continue
                ProjectReference.objects.create(
                    project=project,
                    title=title,
                    citation=citation,
                    url=url,
                )
    
            appendices = payload.get("appendices") or []
            if job.file:
                ProjectAsset.objects.create(
                    project=project,
                    asset_type="Report",
                    file=job.file,
                    mime_type=job.file.content_type or "application/pdf",
                    file_size=job.file.size,
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