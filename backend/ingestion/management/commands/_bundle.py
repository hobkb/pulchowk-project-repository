"""
Shared vocabulary for portable project bundles.

Three people ingesting different PDFs on three local databases cannot merge
by shipping SQL: every database numbers its rows from 1, so the primary
keys collide, and the same supervisor extracted on two machines becomes two
different rows that split his project list in the catalogue.

A bundle sidesteps both problems by never moving an id. Everything is
addressed by a NATURAL key -- a person by roll number or name, a keyword by
its word, a department by its canonical name -- and the importing database
assigns its own ids. That makes the merge order-independent and repeatable:
importing the same bundle twice changes nothing the second time.
"""

import hashlib
import re

BUNDLE_VERSION = 1

MANIFEST_NAME = "manifest.json"
PROJECT_DIR = "projects"
PDF_DIR = "pdfs"


def normalize_key(value):
    """Casefolded, whitespace-collapsed form used for natural-key matching."""
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def project_identity(*, title, batch, file_hash=None):
    """A stable identity for one project, independent of any database.

    The PDF's content hash is preferred: two people who happen to ingest
    the same report must not end up with two copies of it. Where no hash
    was recorded, the title and batch together are the best available
    stand-in.
    """
    if file_hash:
        return f"sha:{file_hash}"
    basis = f"{normalize_key(title)}|{normalize_key(batch)}"
    return "tb:" + hashlib.sha1(basis.encode("utf-8")).hexdigest()


def person_identity(person_data):
    """A stable identity for one person.

    A roll number is issued by the campus and is unique by construction, so
    it wins where present. Faculty have no such number, leaving the name --
    which is why the importer only ever ADDS to a matched faculty record and
    never overwrites, keeping a wrong match cheap to correct.
    """
    roll = normalize_key(person_data.get("roll_number"))
    if roll:
        return f"roll:{roll}"
    email = normalize_key(person_data.get("email"))
    if email:
        return f"email:{email}"
    return f"name:{normalize_key(person_data.get('full_name'))}"
