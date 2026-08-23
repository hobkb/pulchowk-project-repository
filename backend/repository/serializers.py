from django.core.exceptions import ObjectDoesNotExist
from rest_framework import serializers

import re

from repository.models import (
    Project,
    ProjectPerson,
    ProjectReference,
    ProjectSection,
)

PERSON_FACULTY_ROLES = {
    "Supervisor",
    "Co-Supervisor",
    "Faculty Author",
    "Industry Mentor",
}

_RESULTS_CANONICAL = {
    "results",
    "results and discussion",
    "discussion",
    "key findings",
    "findings",
    "experiments",
    "experimental results",
}

_CONCLUSION_CANONICAL = {
    "conclusion",
    "conclusion and future work",
}


def batch_to_year(batch):
    """Convert a roll batch (e.g. "078") to a display year (e.g. "2078")."""
    if not batch:
        return None
    b = str(batch).strip()
    if b.isdigit() and len(b) >= 2:
        return "20" + b[-2:]
    return b or None


def flatten_text(value):
    """Collapse extracted whitespace/newlines into single spaces so text flows naturally."""
    if not value:
        return value
    return re.sub(r"\s+", " ", str(value)).strip()


def _section_content(project, preferred):
    ordered = project.sections.all().order_by("display_order")
    for pref in preferred:
        for section in ordered:
            if section.canonical_section and section.canonical_section.strip().lower() == pref and section.content.strip():
                return section.content.strip()
    for section in ordered:
        if section.canonical_section and section.canonical_section.strip().lower() in preferred:
            if section.content.strip():
                return section.content.strip()
    return ""


class ProjectPersonSerializer(serializers.Serializer):
    name = serializers.CharField(source="person.full_name")
    roll_number = serializers.SerializerMethodField()
    rollNumber = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    role = serializers.CharField()
    display_order = serializers.IntegerField()

    def get_roll_number(self, obj):
        roll = getattr(obj.person, "roll_number", None)
        if roll:
            return roll
        email = obj.person.email or ""
        if email:
            prefix = email.split("@")[0].split(".")[0]
            if prefix and prefix.isalnum():
                return prefix.upper()
        return ""

    def get_rollNumber(self, obj):
        return self.get_roll_number(obj)

    def get_email(self, obj):
        return obj.person.email or ""


class ProjectSectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectSection
        fields = [
            "id",
            "heading",
            "canonical_section",
            "heading_level",
            "display_order",
            "content",
            "page_start",
            "page_end",
            "word_count",
        ]


def build_section_tree(rows):
    """Rebuilds the nested section tree from the flat ProjectSection rows.

    ProjectSection has no parent FK, but it does not need one: rows are
    written in document order (a single pre-order `display_order`
    sequence, assigned by the publish view) and each carries its
    heading_level. That pair is enough to reconstruct the exact tree with
    the same open-section stack the ingestion pipeline used to build it in
    the first place -- a heading either opens a sibling at its own level,
    a child of whatever is currently deepest-open, or closes deeper levels
    back up to its own.

    A level that would leave an impossible gap (a level-3 heading with no
    level-2 open) is clamped to the deepest legal level rather than
    dropped, mirroring the ingestion-side rule, so a section can never
    vanish from the published document just because its recorded level is
    inconsistent.
    """
    root = []
    stack = []  # list[(level, node)], shallowest-open first

    for row in rows:
        node = dict(row)
        level = node.get("heading_level") or 1
        if not isinstance(level, int) or level < 1:
            level = 1
        max_allowed = (stack[-1][0] + 1) if stack else 1
        level = min(level, max_allowed)

        node["heading_level"] = level
        node["children"] = []

        while stack and stack[-1][0] >= level:
            stack.pop()
        if stack:
            stack[-1][1]["children"].append(node)
        else:
            root.append(node)
        stack.append((level, node))

    return root


class ProjectReferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectReference
        fields = ["title", "citation", "url"]


class ProjectListSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(read_only=True)
    authors = serializers.SerializerMethodField()
    supervisor = serializers.SerializerMethodField()
    supervisors = serializers.SerializerMethodField()
    year = serializers.SerializerMethodField()
    department = serializers.SerializerMethodField()
    cluster = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    resultsSummary = serializers.SerializerMethodField()
    abstract = serializers.SerializerMethodField()
    technologies = serializers.SerializerMethodField()
    keywords = serializers.SerializerMethodField()
    coverImage = serializers.SerializerMethodField()
    pdfUrl = serializers.SerializerMethodField()
    accessStatus = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            "id",
            "title",
            "authors",
            "supervisor",
            "supervisors",
            "year",
            "batch",
            "department",
            "cluster",
            "status",
            "abstract",
            "resultsSummary",
            "technologies",
            "keywords",
            "coverImage",
            "pdfUrl",
            "accessStatus",
        ]

    def get_people(self, obj, roles=None):
        people = list(
            obj.project_people.all().select_related("person").order_by("display_order")
        )
        if roles:
            people = [pp for pp in people if pp.role in roles]
        return people

    def get_authors(self, obj):
        people = [pp for pp in self.get_people(obj) if pp.role == "Author"]
        return ProjectPersonSerializer(people, many=True).data

    def get_supervisors(self, obj):
        people = [
            pp for pp in self.get_people(obj)
            if pp.role in PERSON_FACULTY_ROLES
        ]

        designation_map = {
            "Assistant Professor": "Asst. Prof.",
            "Associate Professor": "Assoc. Prof.",
            "Professor": "Prof.",
        }

        supervisors = []

        for pp in people:

            person = pp.person
            # Person -> Faculty is multi-table inheritance, so this accessor
            # raises Faculty.DoesNotExist (not AttributeError) when the
            # person is not a faculty member -- a plain Person recorded as an
            # Industry Mentor would have crashed the whole response, and
            # getattr's default cannot catch that.
            try:
                faculty = person.faculty
            except ObjectDoesNotExist:
                faculty = None

            designation = ""
            title = ""

            if faculty:
                designation = designation_map.get(
                    faculty.designation,
                    faculty.designation or ""
                )
                title = faculty.title or ""

            parts = [designation, title, person.full_name]
            supervisors.append(" ".join(part for part in parts if part).strip())

        return supervisors
    
    def get_supervisor(self, obj):
        names = self.get_supervisors(obj)
        return ", ".join(names)

    def get_year(self, obj):
        return batch_to_year(obj.batch)

    def get_department(self, obj):
        if obj.department:
            return obj.department.name
        return ""

    def get_cluster(self, obj):
        """The project's research cluster.

        `Project.cluster` is the real, validated field. The domain /
        research-group fallbacks are kept only so projects published before
        the field existed still report something rather than going blank.
        """
        if obj.cluster:
            return obj.cluster
        domain = obj.project_domains.order_by("id").first()
        if domain:
            return domain.domain.name
        if obj.research_group:
            return obj.research_group.name
        return ""

    def get_status(self, obj):
        return obj.status

    def get_resultsSummary(self, obj):
        """Kept in the response shape for compatibility, but always empty
        for an unprivileged caller.

        This used to return the raw text of the report's Results (or
        Conclusion) section to anyone who listed projects -- confidential
        report body, served from the public catalogue endpoint. Only
        reviewers see it now; the abstract is what the public record
        summarises a project with.
        """
        if not self._is_privileged():
            return ""
        return _section_content(obj, _RESULTS_CANONICAL) or _section_content(
            obj, _CONCLUSION_CANONICAL
        )

    def _is_privileged(self):
        """See ProjectDetailSerializer._is_privileged -- defined here too so
        the list serializer can apply the same rule without importing it."""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return False
        if user.is_staff or user.is_superuser or getattr(user, "role", None) == "admin":
            return True
        person_id = getattr(user, "person_id", None)
        if person_id is None:
            return False
        from organization.models import DepartmentAdmin

        return DepartmentAdmin.objects.filter(faculty_id=person_id, is_active=True).exists()

    def get_abstract(self, obj):
        return flatten_text(obj.abstract)

    def get_technologies(self, obj):
        return list(
            obj.project_keywords.order_by("id").values_list("keyword__name", flat=True)
        )

    def get_keywords(self, obj):
        return self.get_technologies(obj)

    def get_coverImage(self, obj):
        return None

    def get_pdfUrl(self, obj):
        """The report file, for reviewers and for readers whose access
        request was approved.

        An approval has to actually do something, otherwise it is just a
        message; this is what it does.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return None

        allowed = self._is_privileged()
        if not allowed:
            from repository.models import ProjectAccessRequest

            allowed = ProjectAccessRequest.objects.filter(
                project=obj,
                requester=user,
                status=ProjectAccessRequest.Status.APPROVED,
            ).exists()

        if not allowed:
            return None

        report = obj.assets.filter(asset_type="Report").first()
        if report and report.file:
            return report.file.url
        return None

    def get_accessStatus(self, obj):
        """How the requesting user stands with this report: "granted" for a
        reviewer or an approved requester, otherwise their request state."""
        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return "anonymous"
        if self._is_privileged():
            return "granted"

        from repository.models import ProjectAccessRequest

        latest = (
            ProjectAccessRequest.objects.filter(project=obj, requester=user)
            .order_by("-created_at")
            .first()
        )
        if latest is None:
            return "none"
        return {
            ProjectAccessRequest.Status.APPROVED: "granted",
            ProjectAccessRequest.Status.PENDING: "pending",
            ProjectAccessRequest.Status.DECLINED: "declined",
        }[latest.status]


class ProjectDetailSerializer(ProjectListSerializer):
    sections = serializers.SerializerMethodField()
    sections_restricted = serializers.SerializerMethodField()
    references = serializers.SerializerMethodField()
    domains = serializers.SerializerMethodField()
    academic_level = serializers.CharField(read_only=True)
    project_type = serializers.CharField(read_only=True)
    language = serializers.CharField(read_only=True)
    github_url = serializers.URLField(read_only=True, default="")
    doi_url = serializers.URLField(read_only=True, default="")
    publication_url = serializers.URLField(read_only=True, default="")
    demo_url = serializers.URLField(read_only=True, default="")
    updated_at = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Project
        fields = ProjectListSerializer.Meta.fields + [
            "sections",
            "sections_restricted",
            "references",
            "domains",
            "academic_level",
            "project_type",
            "language",
            "github_url",
            "doi_url",
            "publication_url",
            "demo_url",
            "updated_at",
        ]

    def get_sections_restricted(self, obj):
        """True when the report body is being withheld from this requester,
        so a client can say so honestly instead of rendering an empty
        document and implying the report has no content."""
        return not self._is_privileged()

    def get_sections(self, obj):
        """The report's own section tree -- Introduction, Methodology,
        Results and the rest.

        This is the confidential body of a student's project report and is
        served ONLY to reviewers. It was previously returned to every
        caller, signed in or not, which published the full extracted text
        of every report in the repository through the public detail
        endpoint. Withholding it in the interface alone would not have
        helped: anyone could still read it straight from the API.

        The abstract is deliberately NOT part of this -- it stays on the
        public record as the readable academic summary.
        """
        if not self._is_privileged():
            return []
        sections = obj.sections.order_by("display_order", "id")
        rows = ProjectSectionSerializer(sections, many=True).data
        return build_section_tree(rows)

    def get_references(self, obj):
        # Part of the report body, and withheld on the same rule.
        if not self._is_privileged():
            return []
        return ProjectReferenceSerializer(obj.references.all(), many=True).data

    def get_domains(self, obj):
        return list(
            obj.project_domains.values_list("domain__name", flat=True)
        )