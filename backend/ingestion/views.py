from django.db import transaction
from django.utils.text import slugify
from rest_framework.views import APIView
from rest_framework import permissions, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from accounts.models import Faculty, Person, Student
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
import mimetypes, re
from ingestion.pipeline.utils.text_cleaners import (
    clean_roll_number,
    normalize_canonical_section,
    normalize_person_name,
)

from core.responses import success_response


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


def is_admin_or_dept_admin(user):
    if not user or not user.is_authenticated:
        return False
    if user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin":
        return True
    person = getattr(user, "person", None)
    if person is not None:
        from organization.models import DepartmentAdmin
        return DepartmentAdmin.objects.filter(faculty=person, is_active=True).exists()
    return False


def get_job_for_user(job_id, user):
    try:
        if is_admin_or_dept_admin(user) or IngestionJob.objects.filter(id=job_id, uploaded_by=user).exists():
            return IngestionJob.objects.get(id=job_id)

        raise NotFound("Job not found.")
    
    except IngestionJob.DoesNotExist:
        raise NotFound("Job not found.")


class JobListCreateAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        if not is_admin_or_dept_admin(request.user):
            raise ValidationError({"detail": "Only admins or departmental admins can upload projects."})
        serializer = IngestionJobCreateSerializer(data=request.data)
    
        if not serializer.is_valid():
            raise ValidationError(serializer.errors)
    
        uploaded_file = serializer.validated_data["file"]
    
        job = IngestionJob.objects.create(
            file=uploaded_file,
            original_filename=uploaded_file.name,
            uploaded_by=request.user,
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
            if is_admin_or_dept_admin(request.user)
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
    
        if job.status not in (
            IngestionJob.Status.EXTRACTED,
            IngestionJob.Status.SECTIONS_PENDING,
        ):
            raise ValidationError(
                {
                    "detail": (
                        "Cannot edit payload unless job status is "
                        f"EXTRACTED or SECTIONS_PENDING. Current status: {job.status}"
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
           project_sections = serializer.validated_data["project_sections"]

           for section in project_sections:
                if "content" in section:
                    section["word_count"] = len(
                        re.findall(r"\w+", section["content"])
                    )

           payload["project_sections"] = project_sections

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
    
        # Persist raw extra flags directly (not part of strict serializer)
        if "_sections_skipped" in request.data:
            payload["_sections_skipped"] = bool(request.data["_sections_skipped"])
        if "_verified_by_admin" in request.data:
            payload["_verified_by_admin"] = bool(request.data["_verified_by_admin"])

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
    STUDENT_ROLES = {"author", "student"}
    
    FACULTY_ROLES = {
                    "faculty",
                    "supervisor",
                    "co-supervisor",
                    "co supervisor",
                }
    
    @staticmethod
    def _iter_sections(sections):
        for section in sections:
            if not isinstance(section, dict):
                continue
            yield section
            yield from JobPublishAPIView._iter_sections(section.get("children") or [])

    @classmethod
    def _create_sections(cls, project, sections):
        for index, section_data in enumerate(sections, start=1):
            if not isinstance(section_data, dict):
                continue
            heading = section_data.get("heading", f"Section {index}")
            canonical_section = section_data.get("canonical_section")
            ProjectSection.objects.create(
                project=project,
                heading=normalize_person_name(heading),
                canonical_section=normalize_canonical_section(canonical_section),
                heading_level=section_data.get("heading_level", 1),
                display_order=section_data.get("display_order", index),
                content=section_data.get("content", ""),
                page_start=section_data.get("page_start"),
                page_end=section_data.get("page_end"),
                word_count=section_data.get("word_count", 0),
            )
            cls._create_sections(project, section_data.get("children") or [])
            
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
    
        if sections:
            for index, section in enumerate(self._iter_sections(sections)):
                heading_level = section.get("heading_level") or 1
                if not isinstance(heading_level, int) or heading_level < 1 or heading_level > 6:
                    errors.setdefault("project_sections", []).append(
                        f"Section {index + 1} has an invalid heading level."
                    )
                    break

        if errors:
            raise ValidationError(errors)
    
    @staticmethod
    def get_or_create_student(
        *,
        full_name,
        department,
        roll_number,
        academic_level,
    ):
        roll_number = clean_roll_number(roll_number) if roll_number else ""
        academic_level = academic_level or "UG"

        email = None
        if roll_number:
            email_roll = roll_number
            if email_roll.upper().startswith("PUL"):
                email_roll = email_roll[3:]

            first_name = full_name.split()[0].lower()
            email = f"{email_roll.lower()}.{first_name}@pcampus.edu.np"

        if roll_number:
            student, _ = Student.objects.update_or_create(
                roll_number=roll_number,
                defaults={
                    "full_name": full_name,
                    "department": department,
                    "academic_level": academic_level,
                    "email": email,
                },
            )
            return student

        student, _ = Student.objects.update_or_create(
            full_name=full_name,
            academic_level=academic_level,
            defaults={
                "department": department,
                "email": email,
            },
        )

        return student

    TITLE_TOKEN_RE = re.compile(
        r'^(?P<title>(?:Prof(?:essor)?\.?|Dr\.?|Er\.?|Engr\.?|Mr\.?|Mrs\.?|Ms\.?|Miss|Drs\.?|Rev\.?|Hon\.?)'
        r'(?:\s+(?:Prof(?:essor)?\.?|Dr\.?|Er\.?|Engr\.?|Mr\.?|Mrs\.?|Ms\.?|Miss|Drs\.?|Rev\.?|Hon\.?))*)\s+(?P<name>.+)$',
        re.IGNORECASE,
    )

    @staticmethod
    def _normalize_full_name(full_name):
        return normalize_person_name(full_name)

    @classmethod
    def _parse_faculty_full_name(cls, full_name):
        cleaned = str(full_name or "").strip()
        if not cleaned:
            return "", ""

        match = cls.TITLE_TOKEN_RE.match(cleaned)
        if not match:
            return cls._normalize_full_name(cleaned), ""

        title = match.group("title").strip()
        name = cls._normalize_full_name(match.group("name").strip())
        return name, title

    @staticmethod
    def get_or_create_faculty(
        *,
        full_name,
        department,
        designation,
        title="",
    ):

        faculty = Faculty.objects.filter(
            full_name=full_name,
            department=department,
        ).first()

        if faculty is not None:
            updated = False
            if designation and not faculty.designation:
                faculty.designation = designation
                updated = True
            if title and not faculty.title:
                faculty.title = title
                updated = True
            if updated:
                faculty.save()
            return faculty

        return Faculty.objects.create(
            full_name=full_name,
            department=department,
            designation=designation,
            title=title,
        )

    @staticmethod
    def get_or_create_person(
        *,
        full_name,
        department,
    ):
        person, _ = Person.objects.update_or_create(
            full_name=full_name,
            defaults={
                "department": department,
            },
        )

        return person
    
    def post(self, request, job_id):
        job = get_job_for_user(job_id, request.user)
    
        if job.published_project is not None and job.status != IngestionJob.Status.SECTIONS_PENDING:
            raise ValidationError(
                {
                    "detail": (
                        "This job has already been published."
                    )
                }
            )
        if job.status not in (
            IngestionJob.Status.EXTRACTED,
            IngestionJob.Status.SECTIONS_PENDING,
        ):
            raise ValidationError(
                {
                    "detail": (
                        "Job can only be published when status is "
                        f"EXTRACTED or SECTIONS_PENDING. Current status: {job.status}"
                    )
                }
            )

        # ── Case B: SECTIONS_PENDING → update sections on existing project ──
        if job.status == IngestionJob.Status.SECTIONS_PENDING:
            payload = job.extracted_payload or {}
            project = job.published_project
            if project is None:
                raise ValidationError({"detail": "No published project found for this job."})

            with transaction.atomic():
                # Replace all existing sections
                project.sections.all().delete()
                self._create_sections(project, payload.get("project_sections", []))

                job.status = IngestionJob.Status.VERIFIED
                job.save(update_fields=["status", "updated_at"])

                IngestionJobLog.objects.create(
                    job=job,
                    level="INFO",
                    message=(
                        f"Sections updated on Project ({project.id}) by "
                        f"{request.user.email}. Status set to VERIFIED."
                    ),
                )

            return success_response(
                data={"project_id": str(project.id)},
                message="Project sections updated and status set to Verified.",
                status=status.HTTP_200_OK,
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
            campus = Campus.objects.filter(name__iexact=campus_name).first()

            department = None
            if department_name:
                department = Department.objects.filter(
                    name__iexact=department_name
                ).first()

                if campus and department is not None and department.campus_id != campus.id:
                    department = None

                if department is None and campus is not None:
                    department = Department.objects.filter(
                        campus=campus,
                        name__iexact=department_name,
                    ).first()

            if department is None and campus is not None:
                department = Department.objects.filter(campus__iexact=campus).first()

            if department is None:
                department = Department.objects.first()

            research_group = None
            if research_group_name and department is not None:
                research_group = ResearchGroup.objects.filter(
                    department=department,
                    name=research_group_name,
                ).first()
    
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
                extraction_verified_by=request.user,
            )

            self._create_sections(project, payload.get("project_sections", []))
               
            people = payload.get("people_and_roles") or []
        
            for person_data in people:
                raw_full_name = (person_data.get("full_name") or "").strip()
                role = (person_data.get("role") or "Author").strip()
                role_lower = role.lower()
                designation = (person_data.get("designation") or "").strip()
                academic_level = (person_data.get("academic_level") or "UG").strip()
                roll_number = clean_roll_number(
                    (person_data.get("roll_number") or "").strip()
                )

                if role_lower in self.FACULTY_ROLES:
                    full_name, title = self._parse_faculty_full_name(raw_full_name)
                else:
                    full_name = self._normalize_full_name(raw_full_name)
                    title = ""

                if not full_name:
                    continue

                if role_lower in self.STUDENT_ROLES:
                    person = self.get_or_create_student(
                        full_name=full_name,
                        department=department,
                        roll_number=roll_number,
                        academic_level=academic_level,
                    )

                elif role_lower in self.FACULTY_ROLES:
                    person = self.get_or_create_faculty(
                        full_name=full_name,
                        department=department,
                        designation=designation,
                        title=title,
                    )

                else:
                    person = self.get_or_create_person(
                        full_name=full_name,
                        department=department,
                    )

                ProjectPerson.objects.update_or_create(
                    project=project,
                    person=person,
                    role=role,
                    defaults={
                        "display_order": person_data.get("display_order", 1),
                    },
                )
            keywords = [value for value in (payload.get("keywords") or []) if str(value).strip()]
            if keywords:
                for keyword_name in keywords:
                    keyword_name = str(keyword_name).strip()
                    if not keyword_name:
                        continue

                    keyword, _ = Keyword.objects.get_or_create(name=keyword_name)
                    ProjectKeyword.objects.get_or_create(
                        project=project,
                        keyword=keyword,
                    )
                    
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
                mime_type, _ = mimetypes.guess_type(job.file.name)
                ProjectAsset.objects.create(
                    project=project,
                    asset_type="Report",
                    file=job.file.name,
                    mime_type=mime_type or "application/pdf",
                    file_size=job.file.size,
                )
    
            # ── Case A: set final status based on whether sections were skipped ──
            sections_skipped = bool(payload.get("_sections_skipped"))
            new_status = (
                IngestionJob.Status.SECTIONS_PENDING
                if sections_skipped
                else IngestionJob.Status.VERIFIED
            )

            job.published_project = project
            job.status = new_status
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
                    f"Status set to {new_status}."
                ),
            )
    
        return success_response(
            data={
                "project_id": str(project.id),
            },
            message="Project published successfully.",
            status=status.HTTP_200_OK,
        )