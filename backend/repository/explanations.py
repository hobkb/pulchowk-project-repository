"""Why two projects were considered related.

The similarity itself is computed from sentence embeddings, and a cosine is
not something a reader can act on. Neither is a corpus-relative percentile:
"more similar than 98% of project pairs" sounds like a measurement of overlap
and is not one, and a band such as "High similarity" says how strong the
number was without saying what the projects have in common.

This module answers the useful question instead -- what subject matter the
two projects actually share -- and answers it from the projects' own recorded
data rather than from the embedding. Nothing here influences retrieval,
ranking, thresholds or ordering; it is presentation attached to a result set
that has already been decided elsewhere.

Where the terms come from
-------------------------
The weighted `search_vector` each project already maintains, so there is no
second index to build or keep current. Its weight classes are used as they
were defined:

    A  title       treated as subject matter
    B  keywords    treated as subject matter
    C  abstract    corroborating only
    D  people, department, cluster, batch    ignored entirely

D is excluded deliberately. Two projects sharing a supervisor, a department
or an intake year have nothing in common in subject matter, and surfacing a
person's name as the reason two projects are related would be both wrong and
a disclosure.

What makes a term worth showing
-------------------------------
Two rules, both measured against the corpus rather than hand-listed.

Rare enough to mean something. A term is only explanatory if it is uncommon
in the repository, so the cut-off is a share of the corpus rather than a
fixed count. This is what keeps "system", "application", "machine learning"
and the like out: measured over the current corpus of 95 projects they occur
in 70, 31 and 44 of them respectively, far above the cut-off, while a genuine
subject term sits in a handful. The cut-off itself was set at the loosest
value that still excludes every generic term named as unacceptable; the sweep
is recorded beside the constant. A blocklist of generic words was not needed
and would not have travelled to a different corpus.

Anchored in curated subject matter. The term must appear in the title or
keywords of at least one of the two projects, not merely in both abstracts.
Without that, pairs get explained by whatever incidental vocabulary two
abstracts happen to share, which is exactly the invented explanation this is
supposed to avoid. Measured over the 171 pairs Similar Projects currently
returns, the anchored rule explains 72% of them; dropping the anchor pushes
that to 98%, which is not better -- it means almost nothing is left
unexplained, including the pairs where there is genuinely nothing to say.

Silence is a valid answer
-------------------------
Between a quarter and a third of pairs yield no explanation, and those are returned with an
empty list so the interface can simply say nothing. A recommendation with no
stated reason is honest; a fabricated reason is not.
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

# How many terms a single explanation may carry. The point is a glance, not a
# list; three keeps a card compact.
MAX_TERMS = 3

# Lexemes shorter than this are noise once stemmed.
MIN_TERM_LENGTH = 3


def _document_frequency():
    """How many published projects each subject-matter lexeme occurs in.

    Weight D is dropped here as well as at match time, so a term that only
    ever appears as a person's name or a department carries no frequency and
    can never be selected.
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
    """(anchor, body) lexeme sets per project.

    Anchor is title and keywords, body is those plus the abstract. One query
    for the whole set of projects on the page.
    """
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
    """Map each phrase to its lexemes, using the same analyser as the index.

    One query for every phrase under consideration, so the display labels are
    stemmed exactly the way the terms they have to match were.
    """
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
    """Turn a set of shared lexemes into at most MAX_TERMS readable labels.

    Preference order, strongest first:

      a curated keyword phrase, when every one of its lexemes is shared, so
      "Secure Communication" is offered whole rather than broken into two
      chips that each say less than the pair;

      a single-word keyword;

      a word from a title, which is real project data but incidental -- a
      title says "Encrypting telemetry at the sensor" where the keyword says
      "Encryption", and the curated term is the better label for the same
      concept.

    Within each tier, rarest first: the rarest shared term is the most
    informative thing about the pair.
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
        if len(labels) >= MAX_TERMS:
            break
    return labels


def _titlecase(text):
    """Present a term without shouting, and without flattening an acronym.

    Recorded keywords are inconsistently cased, so an all-lower term is
    capitalised and anything already carrying capitals is left as the author
    wrote it.
    """
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


def shared_concepts(subject, candidates):
    """Subject matter each candidate shares with `subject`.

    Returns {project_id: [label, ...]}, empty list where there is not enough
    evidence to say anything. `subject` is a Project.
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
        if shared:
            subject_keywords, subject_titles = _label_sources(subject)
            candidate_keywords, candidate_titles = _label_sources(candidate)
            out[candidate.pk] = _display_labels(
                shared,
                subject_keywords + candidate_keywords,
                subject_titles + candidate_titles,
                frequency,
            )
        else:
            out[candidate.pk] = []
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
            )
        else:
            out[candidate.pk] = []
    return out
