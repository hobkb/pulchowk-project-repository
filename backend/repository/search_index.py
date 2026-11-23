"""The lexical half of search: a PostgreSQL full-text index over a project.

Why this exists
---------------
Keyword search was previously a chain of `icontains` filters, one per query
term, over four multi-valued relations. Each chained filter adds a join, so
row count is combinatorial in the number of terms. Measured on the live
catalogue before this module existed:

    "machine learning"     5,456 rows for   14 projects     0.8 s
    "image"                  660 rows for   26 projects     0.2 s
    "deep learning model" 665,791 rows for   21 projects    62.5 s

Results were correct -- the view applied `.distinct()` -- but a three-word
query took over a minute. A `tsvector` column with a GIN index replaces the
joins with one indexed lookup and yields a relevance score.

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

import math

from django.contrib.postgres.search import SearchQuery, SearchVector
from django.db import connection
from django.db.models import Value
from django.db.models.expressions import RawSQL

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


def _term_frequencies(terms):
    """How many published projects each term matches, and the corpus size.

    One round trip for the whole query. The counts drive both the ranking
    weights and the prefix-expansion decision.
    """
    from repository.models import Project

    if not terms:
        return {}, 0
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT t.term,
                   (SELECT COUNT(*) FROM projects p
                     WHERE p.status = 'Published'
                       AND p.search_vector @@ to_tsquery('english', t.term)),
                   (SELECT COUNT(*) FROM projects p
                     WHERE p.status = 'Published'
                       AND p.search_vector @@ to_tsquery('english', t.term || ':*'))
            FROM unnest(%s::text[]) AS t(term)
            """,
            [list(terms)],
        )
        counts = {
            row[0]: {"exact": row[1], "prefix": row[2]}
            for row in cursor.fetchall()
        }
    corpus = Project.objects.filter(status="Published").count()
    return counts, corpus


def _idf(document_frequency, corpus):
    """Inverse document frequency, floored so a ubiquitous term still counts.

    A term matching almost everything approaches ln(2) rather than zero: it
    should stop dominating the ranking, not stop contributing to it.
    """
    if corpus <= 0:
        return 1.0
    return math.log(1.0 + corpus / max(1, document_frequency))


def query_terms(text):
    """The sanitised, non-empty terms of a query, in order."""
    return [t for t in text.translate(_TSQUERY_UNSAFE).split() if t]


def _expressions(text):
    """Per-term tsquery strings for `text`, with prefix expansion where it is
    warranted, plus the corpus statistics used to weight them.

    Prefix expansion is a fallback, not the default. `term:*` matches an
    unfinished word and is what lets a partial surname find its owner, but
    applied to a word already present in the corpus it only broadens the
    query. The final term is therefore expanded only when it matches nothing
    on its own, which is what actually indicates an incomplete word.

    This was previously unconditional, because the search box searched as the
    reader typed. It no longer does, so the common case is a finished word.
    """
    terms = query_terms(text)
    if not terms:
        return [], {}, 0

    counts, corpus = _term_frequencies(terms)
    expressions = []
    for index, term in enumerate(terms):
        stats = counts.get(term, {"exact": 0, "prefix": 0})
        last = index == len(terms) - 1
        if last and stats["exact"] == 0 and stats["prefix"] > 0:
            expressions.append((term + ":*", stats["prefix"]))
        else:
            expressions.append((term, stats["exact"]))
    return expressions, counts, corpus


def search_query(text):
    """Parse a user query into a tsquery.

    Terms are ANDed. Input is stripped of tsquery operators first, so a stray
    colon or parenthesis cannot produce a syntax error from ordinary typing.

    This builds the query itself rather than using `websearch_to_tsquery`,
    which has no way to express the prefix match that partial-word queries
    depend on.
    """
    expressions, _counts, _corpus = _expressions(text)
    if not expressions:
        return SearchQuery("", search_type="plain", config=SEARCH_CONFIG)

    joined = " & ".join(expression for expression, _df in expressions)
    return SearchQuery(joined, search_type="raw", config=SEARCH_CONFIG)


def lexical_queryset(queryset, text):
    """Projects matching `text`, ranked by rarity-weighted lexical relevance.

    `ts_rank_cd` is cover density ranking: it rewards matched terms appearing
    close together and honours the A/B/C/D weight classes, but it has no
    notion of how ordinary a term is. Ranking on it alone lets a common word
    carry the same authority as a distinctive one, so "sentiment analysis
    system" is scored partly on "system", which most of the catalogue
    contains.

    Each term is therefore scored separately and weighted by its inverse
    document frequency before summing. Influence falls out of corpus
    statistics, so no vocabulary list is involved. Terms remain ANDed: this
    changes result order, not which projects match.
    """
    expressions, _counts, corpus = _expressions(text)
    if not expressions:
        return queryset.none()

    # Built from the expressions already computed rather than by calling
    # search_query, which would repeat the corpus statistics query.
    query = SearchQuery(
        " & ".join(expression for expression, _df in expressions),
        search_type="raw",
        config=SEARCH_CONFIG,
    )

    clauses, params = [], []
    for expression, document_frequency in expressions:
        clauses.append(
            "%s * ts_rank_cd(\"projects\".\"search_vector\", "
            "to_tsquery('english', %s), 32)"
        )
        params.extend([_idf(document_frequency, corpus), expression])

    return (
        queryset.filter(search_vector=query)
        .annotate(lexical_rank=RawSQL(" + ".join(clauses), params))
        .order_by("-lexical_rank", "-id")
    )
