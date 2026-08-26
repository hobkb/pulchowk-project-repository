"""Why two projects were considered related.

The similarity itself is computed from sentence embeddings, and a cosine is
not something a reader can act on. Neither is a corpus-relative percentile:
"more similar than 98% of project pairs" sounds like a measurement of overlap
and is not one, and a band such as "High similarity" says how strong the
number was without saying what the projects have in common.

This module reports what subject matter two projects actually share, drawn
from their own recorded data rather than from the embedding. Nothing here
influences retrieval, ranking, thresholds or ordering.

Where the terms come from
-------------------------
The weighted `search_vector` each project already maintains, so there is no
second index to keep current. Its weight classes are used as defined:

    A  title       subject matter
    B  keywords    subject matter
    C  abstract    corroborating only
    D  people, department, cluster, batch    ignored entirely

Excluding D is a confidentiality requirement as well as a correctness one.
Two projects sharing a supervisor, department or intake year have nothing in
common in subject matter, and naming a person as the reason two projects are
related would disclose them.

What makes a term worth showing
-------------------------------
Three rules, all measured against the corpus rather than hand-listed, so no
blocklist of generic words is needed and none would travel to another corpus.

Rare. A term must occur in no more than MAX_DOCUMENT_FREQUENCY_SHARE of the
corpus. This is what excludes "system", "application" and "machine learning",
which occur in 70, 31 and 44 of the current 95 projects.

Anchored. The term must appear in the title or keywords of at least one of
the pair, not merely in both abstracts, or pairs get explained by whatever
incidental vocabulary two abstracts happen to share. Over the 171 pairs
Similar Projects returns, the anchored rule explains 72%; dropping the anchor
reaches 98%, which means it is explaining pairs that have nothing to say.

Plural. See MIN_SHARED_CONCEPTS.

An empty result is meaningful: callers presenting recommendations drop the
candidate rather than showing it without a reason.
"""

from django.db import connection

# A term must occur in no more than this share of the published corpus to be
# treated as subject matter rather than as background vocabulary.
#
# Chosen by sweeping it against the generic terms it has to keep out. Over the
# current corpus of 95 projects, coverage of the pairs Similar Projects
# returns, and the point at which a generic term is first admitted:
#
#   share   df cut-off   pairs explained   first generic term admitted
#   0.10        9            64.3%         none
#   0.12       11            72.5%         none
#   0.15       14            76.0%         "AI"
#   0.20       19            95.9%         "AI", "web"
#
# 0.12 is therefore the most coverage available before the vocabulary starts
# to degrade. Loosening further buys explanations by admitting exactly the
# words that explain nothing.
MAX_DOCUMENT_FREQUENCY_SHARE = 0.12

# Below this many projects the notion of a "rare" term is meaningless, so no
# explanation is offered at all rather than one drawn from a corpus too small
# to distinguish a subject term from a common one.
MIN_CORPUS_FOR_RARITY = 12

MAX_TERMS = 3

# How many distinct concepts a pair must share to be considered explained.
#
# One shared concept is not evidence of a relationship. Any two projects in an
# engineering catalogue can coincide on a single term, and the rarity cut-off
# cannot separate that from a real overlap: a term can be uncommon in the
# corpus and still be the only thing the pair has in common. Requiring two
# independent concepts is what distinguishes a relationship from a
# coincidence. Counted after phrases are consolidated, so "Secure
# Communication" counts once rather than twice.
MIN_SHARED_CONCEPTS = 2

# Lexemes shorter than this are noise once stemmed.
MIN_TERM_LENGTH = 3


def _document_frequency():
    """How many published projects each subject-matter lexeme occurs in.

    Weight D is dropped here as well as at match time, so a term appearing
    only as a person or department name carries no frequency and can never be
    selected.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT lex.lexeme, COUNT(*)
            FROM projects p, unnest(p.search_vector) AS lex
            WHERE p.status = 'Published'
              AND p.search_vector IS NOT NULL
              AND lex.weights::text ~ '[ABC]'
            GROUP BY lex.lexeme
            """
        )
        frequency = dict(cursor.fetchall())

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM projects "
            "WHERE status = 'Published' AND search_vector IS NOT NULL"
        )
        corpus = cursor.fetchone()[0]

    return frequency, corpus


def _lexemes_by_project(project_ids):
    """(anchor, body) lexeme sets per project: anchor is title and keywords,
    body is those plus the abstract. One query for the whole page."""
    if not project_ids:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.id,
                   array_agg(DISTINCT lex.lexeme)
                       FILTER (WHERE lex.weights::text ~ '[AB]'),
                   array_agg(DISTINCT lex.lexeme)
                       FILTER (WHERE lex.weights::text ~ '[ABC]')
            FROM projects p, unnest(p.search_vector) AS lex
            WHERE p.id = ANY(%s) AND p.search_vector IS NOT NULL
            GROUP BY p.id
            """,
            [list(project_ids)],
        )
        return {
            row[0]: (set(row[1] or []), set(row[2] or []))
            for row in cursor.fetchall()
        }


def _stem(phrases):
    """Map each phrase to its lexemes using the index's analyser, so display
    labels stem the same way as the terms they must match."""
    phrases = [p for p in {p.strip() for p in phrases} if p]
    if not phrases:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT phrase, tsvector_to_array(to_tsvector('english', phrase))
            FROM unnest(%s::text[]) AS phrase
            """,
            [phrases],
        )
        return {row[0]: set(row[1] or []) for row in cursor.fetchall()}


def _display_labels(shared, keyword_sources, title_sources, frequency):
    """Readable labels for a set of shared lexemes, most specific first.

    Preference order: a multi-word keyword phrase whose lexemes are all
    shared, so "Secure Communication" stays whole; then a single-word
    keyword; then a title word. Curated keywords outrank title words because
    a title states a concept incidentally where a keyword names it.

    Within each tier, rarest first.
    """
    stems = _stem(list(keyword_sources) + list(title_sources))
    remaining = set(shared)
    chosen = []

    def take(sources, tier, multiword):
        # Longest phrases first, so a two-word concept is consumed before its
        # halves can be offered separately.
        ordered = sorted(
            (p for p in sources
             if (len(stems.get(p, ())) > 1) == multiword and stems.get(p)),
            key=lambda p: (-len(stems[p]), p.lower()),
        )
        for phrase in ordered:
            lexemes = stems.get(phrase, set())
            if lexemes and lexemes <= remaining:
                rarity = min(frequency.get(t, 0) for t in lexemes)
                chosen.append((tier, rarity, phrase))
                remaining.difference_update(lexemes)

    take(keyword_sources, 0, multiword=True)
    take(keyword_sources, 1, multiword=False)
    take(title_sources, 2, multiword=False)

    chosen.sort(key=lambda row: (row[0], row[1], row[2].lower()))

    labels, seen = [], set()
    for _tier, _rarity, label in chosen:
        cleaned = _titlecase(label)
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(cleaned)
    return labels


def _titlecase(text):
    """Capitalise a term, leaving anything already carrying capitals alone so
    acronyms survive. Recorded keywords are inconsistently cased."""
    words = []
    for word in text.split():
        words.append(word if any(c.isupper() for c in word) else word.capitalize())
    return " ".join(words)


def _label_sources(project):
    """(keyword phrases, title words) -- both the project's own recorded data,
    kept apart because a curated keyword is the better label of the two."""
    keywords = [
        link.keyword.name.strip()
        for link in project.project_keywords.select_related("keyword").all()
        if link.keyword and (link.keyword.name or "").strip()
    ]
    title_words = [
        word.strip(" ,.;:()[]")
        for word in (project.title or "").split()
    ]
    return keywords, [w for w in title_words if w]


def explanations_available():
    """Whether the corpus is large enough for rarity to carry information.

    Below MIN_CORPUS_FOR_RARITY every term looks rare, so no term can be
    distinguished as subject matter. Callers that drop unexplained candidates
    must not do so here: the absence of an explanation means the corpus
    cannot supply one, not that the pairing is weak.
    """
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT COUNT(*) FROM projects "
            "WHERE status = 'Published' AND search_vector IS NOT NULL"
        )
        return cursor.fetchone()[0] >= MIN_CORPUS_FOR_RARITY


def shared_concepts(subject, candidates):
    """Subject matter each candidate shares with `subject`.

    Returns {project_id: [label, ...]}. A candidate that does not share at
    least MIN_SHARED_CONCEPTS distinct concepts maps to an empty list, which
    callers presenting recommendations treat as "there is no case for showing
    this at all" rather than as "show it without a reason".
    """
    candidates = list(candidates)
    if not candidates:
        return {}

    frequency, corpus = _document_frequency()
    if corpus < MIN_CORPUS_FOR_RARITY:
        return {c.pk: [] for c in candidates}
    cutoff = max(1, int(corpus * MAX_DOCUMENT_FREQUENCY_SHARE))

    ids = [subject.pk] + [c.pk for c in candidates]
    lexemes = _lexemes_by_project(ids)
    subject_anchor, subject_body = lexemes.get(subject.pk, (set(), set()))

    out = {}
    for candidate in candidates:
        anchor, body = lexemes.get(candidate.pk, (set(), set()))
        shared = {
            term
            for term in subject_body & body
            if frequency.get(term, 0) <= cutoff
            and len(term) >= MIN_TERM_LENGTH
            and not term.isdigit()
            and (term in subject_anchor or term in anchor)
        }
        labels = []
        if shared:
            subject_keywords, subject_titles = _label_sources(subject)
            candidate_keywords, candidate_titles = _label_sources(candidate)
            labels = _display_labels(
                shared,
                subject_keywords + candidate_keywords,
                subject_titles + candidate_titles,
                frequency,
            )
        out[candidate.pk] = (
            labels[:MAX_TERMS] if len(labels) >= MIN_SHARED_CONCEPTS else []
        )
    return out


def concept_shared_concepts(text, candidates):
    """Subject matter each candidate shares with a free-text idea.

    The same rules, with the reader's own description standing in for the
    subject project. The description is analysed in memory and never stored.
    """
    candidates = list(candidates)
    if not candidates or not (text or "").strip():
        return {c.pk: [] for c in candidates}

    frequency, corpus = _document_frequency()
    if corpus < MIN_CORPUS_FOR_RARITY:
        return {c.pk: [] for c in candidates}
    cutoff = max(1, int(corpus * MAX_DOCUMENT_FREQUENCY_SHARE))

    query_lexemes = _stem([text]).get(text.strip(), set())
    if not query_lexemes:
        return {c.pk: [] for c in candidates}

    lexemes = _lexemes_by_project([c.pk for c in candidates])

    out = {}
    for candidate in candidates:
        anchor, body = lexemes.get(candidate.pk, (set(), set()))
        # Anchored on the project's side: the description has no curated
        # keywords to anchor against, so the term must be subject matter for
        # the project rather than a word its abstract happens to contain.
        shared = {
            term
            for term in query_lexemes & body
            if frequency.get(term, 0) <= cutoff
            and len(term) >= MIN_TERM_LENGTH
            and not term.isdigit()
            and term in anchor
        }
        if shared:
            keywords, titles = _label_sources(candidate)
            out[candidate.pk] = _display_labels(
                shared, keywords, titles, frequency
            )[:MAX_TERMS]
        else:
            out[candidate.pk] = []
    return out
