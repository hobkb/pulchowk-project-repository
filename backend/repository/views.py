from django.db.models import Count, Q
from rest_framework import permissions
from rest_framework.exceptions import NotFound
from rest_framework.views import APIView

from core.responses import paginated_response, success_response
from organization.departments import CANONICAL_DEPARTMENTS
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


# The roles that count as supervising a project, shared by the supervisor
# filter and the supervisor facet.
SUPERVISORY_ROLES = ("Supervisor", "Co-Supervisor")

# Every field a free-text query is matched against. Ordinary case-insensitive
# substring matching over real stored columns -- there is no ranking model,
# no embedding, and no semantic component here, so nothing in the UI should
# describe it as anything other than keyword search.
SEARCH_FIELDS = (
    "title",
    "abstract",
    "batch",
    "cluster",
    "department__name",
    "project_people__person__full_name",
    # A supervisor is looked for by rank as often as by name -- "professor
    # shrestha" and "assoc prof" are both things people type -- so the
    # academic title and designation are searchable alongside the name.
    "project_people__person__faculty__title",
    "project_people__person__faculty__designation",
    "project_keywords__keyword__name",
    "project_domains__domain__name",
)


def apply_search(queryset, query):
    """Filters `queryset` by a free-text keyword query.

    The query is split into whitespace-separated terms and every term must
    match at least one searchable field (AND across terms, OR across
    fields). A single combined `icontains` over the whole string -- what
    this replaced -- meant "solar tracker" only matched records containing
    that exact adjacent phrase, so a project titled "Dual-axis tracker for
    solar arrays" was invisible. Each term is applied as its own `.filter()`
    call rather than one combined Q object, because these are spanning
    multi-valued relations: combining them would require all terms to be
    satisfied by the *same* related row (the same single keyword, the same
    single author), while chained filters let one term match the title and
    another match a keyword.
    """
    for term in query.split():
        term_q = Q()
        for field in SEARCH_FIELDS:
            term_q |= Q(**{f"{field}__icontains": term})
        queryset = queryset.filter(term_q)
    return queryset


# Each filter dimension, keyed by its query parameter, as a function that
# narrows a queryset. Shared by the list endpoint and the facet counts so
# the two can never drift apart in what a filter means.
FILTERS = {
    "department": lambda qs, v: qs.filter(department__name__iexact=v),
    "academic_level": lambda qs, v: qs.filter(academic_level__iexact=v),
    "batch": lambda qs, v: qs.filter(batch__iexact=v),
    # Substring rather than exact: these are values a reader types as well
    # as clicks. A facet click still sends the full value and still matches,
    # but "aiml" typed by hand, or a surname on its own, now works too.
    "cluster": lambda qs, v: qs.filter(cluster__icontains=v),
    # Matched through the supervisory roles only, so a name that also
    # happens to be an author does not pull in unrelated projects.
    "supervisor": lambda qs, v: qs.filter(
        project_people__role__in=SUPERVISORY_ROLES,
        project_people__person__full_name__icontains=v,
    ),
}


def apply_filters(queryset, params, exclude=None):
    """Applies `q` plus every filter in FILTERS present in `params`.

    `exclude` omits one dimension, which is what makes the facet counts
    correct: the number shown beside "Batch 078" must be the number of
    projects that would remain if the user clicked it -- i.e. counted with
    every OTHER active filter applied, but not with the batch filter
    itself, which would otherwise always report either 0 or the current
    result count.
    """
    search = (params.get("q") or "").strip()
    if search:
        queryset = apply_search(queryset, search)

    for name, apply in FILTERS.items():
        if name == exclude:
            continue
        value = (params.get(name) or "").strip()
        if value:
            queryset = apply(queryset, value)
    return queryset


class ProjectListView(APIView):
    """
    Public read-only list of verified (Published) projects.
    Only ingested projects that have been published to the repository
    are surfaced here. Unpublished/processing jobs live in the ingestion app.

    Query parameters (all optional, all server-side):
        q               free-text keyword search -- see apply_search
        department      exact department name
        academic_level  exact academic level (UG / Masters / PhD / Faculty)
        batch           exact batch code (e.g. "078")
        cluster         exact research cluster (AIML / ANLP / NTS / ...)
        supervisor      exact supervisor name
        page            1-based page number (default 1)
        page_size       rows per page (default 12, max 100)
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = apply_filters(get_published_project_queryset(), request.query_params)

        # Spanning a multi-valued relation can duplicate rows; ordering is
        # newest-published-first so the catalogue has a stable, meaningful
        # default rather than whatever order the database returns.
        queryset = queryset.distinct().order_by("-created_at", "-id")

        # Paged in the database rather than in Python: the catalogue grows
        # without bound, and serializing every published project to return
        # twelve of them would get slower with every deposit.
        return paginated_response(
            request,
            queryset,
            lambda rows: ProjectListSerializer(
                rows, many=True, context={"request": request}
            ).data,
            page_size=5,
            message="Projects retrieved successfully.",
        )


class ProjectFacetsView(APIView):
    """
    The filter values that actually occur among published projects, with
    counts -- so the browse page's filters are built from real data instead
    of the full choice lists (which would offer departments and batches
    that match nothing).
    """

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        params = request.query_params
        base = Project.objects.filter(status="Published")

        def counts_for(dimension, field, order):
            """Counts for one facet dimension, computed with every OTHER
            active filter applied, so the number beside an option is
            exactly what selecting it will return."""
            qs = apply_filters(base, params, exclude=dimension)
            rows = (
                qs.exclude(**{f"{field}__isnull": True})
                .exclude(**{field: ""})
                .values(field)
                .annotate(total=Count("id", distinct=True))
                .order_by(order)
            )
            return [
                {"name": row[field], "count": row["total"]}
                for row in rows
                if row[field]
            ]

        departments = counts_for("department", "department__name", "department__name")
        academic_levels = counts_for("academic_level", "academic_level", "academic_level")
        batches = counts_for("batch", "batch", "-batch")
        clusters = counts_for("cluster", "cluster", "cluster")

        # A supervisor is recognised by rank as much as by name, so the
        # academic title and designation travel with the name. `name` stays
        # the bare full name because it is what the `supervisor` filter
        # matches on; `title` and `designation` are for display only.
        supervisor_rows = (
            apply_filters(base, params, exclude="supervisor")
            .filter(project_people__role__in=SUPERVISORY_ROLES)
            .values(
                "project_people__person__full_name",
                "project_people__person__faculty__title",
                "project_people__person__faculty__designation",
            )
            .annotate(total=Count("id", distinct=True))
            .order_by("project_people__person__full_name")
        )

        # One person can appear under several designations across projects
        # (promoted between reports, or recorded inconsistently). They are
        # one filter option, so the rows are merged on the name and the
        # fullest designation seen is the one shown.
        merged = {}
        for row in supervisor_rows:
            name = row["project_people__person__full_name"]
            if not name:
                continue
            entry = merged.setdefault(
                name, {"name": name, "count": 0, "title": "", "designation": ""}
            )
            entry["count"] += row["total"]
            for key, column in (
                ("title", "project_people__person__faculty__title"),
                ("designation", "project_people__person__faculty__designation"),
            ):
                value = (row[column] or "").strip()
                if len(value) > len(entry[key]):
                    entry[key] = value

        supervisors = sorted(merged.values(), key=lambda entry: entry["name"])

        return success_response(
            data={
                # `total` is the number of results for the CURRENT filters,
                # so the page can show a meaningful headline figure.
                "total": apply_filters(base, params).distinct().count(),
                "departments": departments,
                "academic_levels": academic_levels,
                "batches": batches,
                "clusters": clusters,
                "supervisors": supervisors,
                # The full fixed vocabularies, so the upload form and the
                # filter UI never hardcode them on the client.
                "cluster_choices": [c[0] for c in Project.CLUSTERS],
                "department_choices": CANONICAL_DEPARTMENTS,
            },
            message="Repository facets retrieved successfully.",
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
