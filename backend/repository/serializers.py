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
            "heading",
            "canonical_section",
            "heading_level",
            "display_order",
            "content",
            "page_start",
            "page_end",
            "word_count",
        ]


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
        people = [pp for pp in self.get_people(obj) if pp.role in PERSON_FACULTY_ROLES]
        return [pp.person.full_name for pp in people]

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
        domain = obj.project_domains.order_by("id").first()
        if domain:
            return domain.domain.name
        if obj.research_group:
            return obj.research_group.name
        return ""

    def get_status(self, obj):
        return obj.status

    def get_resultsSummary(self, obj):
        return _section_content(obj, _RESULTS_CANONICAL) or _section_content(
            obj, _CONCLUSION_CANONICAL
        )

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
        user = self.context.get("request").user if self.context.get("request") else None
        is_admin = bool(user and (user.is_staff or getattr(user, "role", None) == "admin"))
        if not is_admin:
            return None
        report = obj.assets.filter(asset_type="Report").first()
        if report and report.file:
            return report.file.url
        return None


class ProjectDetailSerializer(ProjectListSerializer):
    sections = serializers.SerializerMethodField()
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

    def get_sections(self, obj):
        sections = obj.sections.order_by("display_order")
        return ProjectSectionSerializer(sections, many=True).data

    def get_references(self, obj):
        return ProjectReferenceSerializer(obj.references.all(), many=True).data

    def get_domains(self, obj):
        return list(
            obj.project_domains.values_list("domain__name", flat=True)
        )