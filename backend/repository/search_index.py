"""The lexical half of search: a PostgreSQL full-text index over a project.

Why this exists
---------------
Keyword search used to be a chain of `icontains` filters, one `.filter()` call
per query term, over four multi-valued relations (people, keywords, domains,
faculty titles). Each chained filter adds another join, so the row count is
combinatorial in the number of terms. Measured on the live catalogue before
this module existed:

    "machine learning"     5,456 rows for   14 projects     0.8 s
    "image"                  660 rows for   26 projects     0.2 s
    "deep learning model" 665,791 rows for   21 projects    62.5 s

The results were correct, because the view applied `.distinct()`, but a
three-word query took over a minute, which is indistinguishable from broken.

A `tsvector` column with a GIN index replaces the joins with one indexed
lookup, and gives a relevance score, which the chained filters never had.

Weighting
---------
Postgres supports four weight classes, and `ts_rank_cd` honours them:

    A  title            the strongest signal a reader gives us
    B  keyword names    curated, few, high precision
    C  abstract         rich but diffuse
    D  department, people, their academic titles and designations,
       cluster code and batch

Weight D exists to preserve what the previous search could do. "adhikari",
"associate professor", "Dr", "AIML" and "078" were all things the old
substring matching found, and all of them would have been lost by indexing
only title, keywords and abstract.

Only catalogue metadata is indexed. Extracted report sections are deliberately
excluded: they are confidential, they would dominate the vector by sheer
length, and the abstract already summarises them.
"""

from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db.models import Value

# The configuration governs stemming and stop words. The corpus is English;
# `language` on Project defaults to "English" for every record.
SEARCH_CONFIG = "english"


def build_search_vector(project):
    """The weighted tsvector for one project, as a database expression.

    Returned as an expression rather than a value so the caller can hand it
    straight to `update()` and let Postgres do the work.
    """
    keywords = " ".join(
        pk.keyword.name
        for pk in project.project_keywords.select_related("keyword").all()
    )

    # Names, and the academic titles and designations that go with them: a
    # supervisor is looked for by rank as often as by name.
    people_terms = []
    for link in project.project_people.select_related("person").all():
        person = link.person
        if not person:
            continue
        if person.full_name:
            people_terms.append(person.full_name)
        faculty = getattr(person, "faculty", None)
        if faculty is not None:
            people_terms.extend(filter(None, [faculty.title, faculty.designation]))

    department = project.department.name if project.department_id else ""
    context = " ".join(
        filter(None, [department, project.cluster or "", project.batch or ""])
    )

    return (
        SearchVector(Value(project.title or ""), weight="A", config=SEARCH_CONFIG)
        + SearchVector(Value(keywords), weight="B", config=SEARCH_CONFIG)
        + SearchVector(Value(project.abstract or ""), weight="C", config=SEARCH_CONFIG)
        + SearchVector(
            Value(" ".join(filter(None, [context, " ".join(people_terms)]))),
            weight="D",
            config=SEARCH_CONFIG,
        )
    )


def update_search_vector(project):
    """Recompute and store one project's search vector.

    Cheap enough to run synchronously on save: it is a single UPDATE and the
    text involved is already in memory.
    """
    from repository.models import Project

    Project.objects.filter(pk=project.pk).update(
        search_vector=build_search_vector(project)
    )


# Characters that are operators inside a tsquery and must not reach it from a
# search box.
_TSQUERY_UNSAFE = str.maketrans({c: " " for c in "&|!()<>:*'\\\""})


def search_query(text):
    """Parse a user query into a tsquery, with the last term as a prefix.

    Terms are ANDed and the final one is matched as a prefix, so "adhik"
    finds Adhikari and a debounced search box narrows as the reader types.
    That behaviour is why this builds the query itself rather than using
    `websearch_to_tsquery`: the websearch parser is friendlier about quoting
    and negation, but it has no way to express a prefix, and losing
    incremental matching on a search-as-you-type box is the worse trade.

    Input is stripped of tsquery operators first, so a stray colon or
    parenthesis cannot produce a syntax error from ordinary typing.
    """
    terms = [t for t in text.translate(_TSQUERY_UNSAFE).split() if t]
    if not terms:
        # Matches nothing rather than raising, and the caller filters on it.
        return SearchQuery("", search_type="plain", config=SEARCH_CONFIG)

    expression = " & ".join(terms[:-1] + [terms[-1] + ":*"])
    return SearchQuery(expression, search_type="raw", config=SEARCH_CONFIG)


def lexical_queryset(queryset, text):
    """Projects matching `text`, ranked by weighted lexical relevance.

    `ts_rank_cd` is cover density ranking: it rewards matched terms appearing
    close together, which suits titles and keyword lists.
    """
    query = search_query(text)
    return (
        queryset.filter(search_vector=query)
        .annotate(lexical_rank=SearchRank(
            "search_vector", query, normalization=Value(32)
        ))
        .order_by("-lexical_rank", "-id")
    )
