"""The text a project is embedded from, and its fingerprint.

Fields were selected against corpus coverage: description, domains and
cluster are populated for 0, 0 and 2 of 95 projects respectively. Sections
are populated but excluded -- a median of 48 per project far exceeds the
model's input window, and the abstract already summarises them.

Department and project type are excluded deliberately, not for lack of
signal: embedding a department name pulls every project in that department
toward every other one, which is what the similarity feature exists to avoid.
Both belong in filters, not in the vector.

Staleness is decided by comparing fingerprints of the embedded string, so any
change to the representation -- including a change to this module -- triggers
regeneration without maintaining a list of watched fields.
"""

import hashlib
import re


def _flat(value):
    # Collapse extracted whitespace: PDF line breaks must not change the
    # fingerprint without changing the meaning.
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def build_text(project, keywords=None):
    """`keywords` may be supplied to avoid a query per project in batch runs."""
    if keywords is None:
        keywords = [
            pk.keyword.name
            for pk in project.project_keywords.select_related("keyword").all()
        ]

    parts = []
    title = _flat(project.title)
    if title:
        parts.append(f"Title: {title}")

    cleaned = [_flat(k) for k in keywords]
    cleaned = [k for k in cleaned if k]
    if cleaned:
        parts.append("Keywords: " + ", ".join(cleaned))

    abstract = _flat(project.abstract)
    if abstract:
        parts.append(f"Abstract: {abstract}")

    return "\n".join(parts)


def build_concept_text(*, concept, title="", description=""):
    """Embedding input for a proposed idea. Concept alone is a complete
    input; title and description are optional."""
    parts = []
    title = _flat(title)
    if title:
        parts.append(title)

    concept = _flat(concept)
    if concept:
        parts.append(concept)

    description = _flat(description)
    if description:
        parts.append(description)

    return " ".join(parts)


def fingerprint(text):
    """Digest of the exact text that was embedded."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
