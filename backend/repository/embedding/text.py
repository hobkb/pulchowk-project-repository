"""The text a project is embedded from, and its fingerprint.

Representation
--------------
A project is embedded from a small, structured block:

    Title: ...
    Keywords: ...
    Abstract: ...

Chosen against the actual corpus rather than by listing every available
field. Measured over the current 95 projects:

    description   0 / 95 populated      -- carries nothing
    domains       0 / 95 populated      -- carries nothing
    cluster       2 / 95 populated      -- carries almost nothing
    sections     94 / 95, median 48 per project

Sections are deliberately excluded. A median of forty-eight per project is
far beyond any sentence-transformer input window, they carry extraction
noise, and the abstract is already the author's own summary of the work.

Department and project type are excluded for a different reason: they are
not noise, they are actively harmful here. Embedding the department name
pulls every project in a department toward every other one, which is the
behaviour the similarity feature exists to remove. Both belong in filters
and badges, never in the vector.

Fingerprint
-----------
`fingerprint()` digests the exact string that gets embedded. Regeneration is
then decided by comparing digests, so it responds to any change in the
representation, including a change to this module, without anyone having to
maintain a list of fields to watch.
"""

import hashlib
import re


def _flat(value):
    """Collapse extracted whitespace so line breaks from the PDF do not
    change the fingerprint without changing the meaning."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def build_text(project, keywords=None):
    """The embedding input for one project.

    `keywords` may be passed in to avoid a query per project when embedding
    in batches; when omitted it is read from the relation.
    """
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
    """The text of a proposed idea, for the Similar Work Check.

    Concept first. A student weighing up an idea rarely has a title, an
    abstract and a keyword list yet, and demanding them turns a thirty-second
    question into writing a proposal. One or two sentences of plain
    description is what people actually have, and it is enough: the whole
    point of a dense retriever is that it does not need the document's own
    vocabulary.

    Title and description stay available for someone who does have them, but
    neither is required and the concept alone is a complete input.
    """
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
