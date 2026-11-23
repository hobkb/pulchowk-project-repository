"""
The canonical department vocabulary and the matching used to map a
free-text department name (from a PDF cover page, or from an older stored
payload) onto one of them.

Kept in one place so the ingestion publish path, the API and any future
consumer agree on what counts as a match. Deliberately conservative: a
name that does not clearly correspond to one of the six returns None so
the reviewer is asked to pick, rather than a project being filed under a
department that was guessed.
"""

import re

CANONICAL_DEPARTMENTS = [
    "Department of Electronics and Computer Engineering",
    "Department of Electrical Engineering",
    "Department of Civil Engineering",
    "Department of Mechanical and Aerospace Engineering",
    "Department of Applied Sciences and Chemical Engineering",
    "Department of Architecture",
]

# The distinguishing words for each department. A candidate must contain
# every word in one of these groups to match it -- "electrical" alone must
# not match "Electronics and Computer", and vice versa.
_SIGNATURES = [
    (("electronics",), "Department of Electronics and Computer Engineering"),
    (("computer",), "Department of Electronics and Computer Engineering"),
    (("electrical",), "Department of Electrical Engineering"),
    (("civil",), "Department of Civil Engineering"),
    (("mechanical",), "Department of Mechanical and Aerospace Engineering"),
    (("aerospace",), "Department of Mechanical and Aerospace Engineering"),
    (("chemical",), "Department of Applied Sciences and Chemical Engineering"),
    (("applied", "science"), "Department of Applied Sciences and Chemical Engineering"),
    (("architecture",), "Department of Architecture"),
]

# Abbreviations that appear on real cover pages.
_ABBREVIATIONS = {
    "doece": "Department of Electronics and Computer Engineering",
    "doece.": "Department of Electronics and Computer Engineering",
    "doeee": "Department of Electrical Engineering",
    "doce": "Department of Civil Engineering",
    "domae": "Department of Mechanical and Aerospace Engineering",
    "doasce": "Department of Applied Sciences and Chemical Engineering",
    "doa": "Department of Architecture",
}


def canonical_department(raw_name):
    """Maps a free-text department name to one of CANONICAL_DEPARTMENTS.

    Returns None when there is no confident match, which the caller should
    treat as "ask the reviewer" rather than as a default.
    """
    if not raw_name:
        return None

    text = re.sub(r"[^a-z\s]", " ", str(raw_name).lower())
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None

    compact = text.replace(" ", "")
    for abbreviation, canonical in _ABBREVIATIONS.items():
        if compact == abbreviation.replace(".", ""):
            return canonical

    # "electronics and computer" must win over the bare "computer" rule, so
    # the most specific signature is preferred when several match.
    matches = []
    for words, canonical in _SIGNATURES:
        if all(word in text for word in words):
            matches.append((len(words), canonical))
    if not matches:
        return None

    matches.sort(key=lambda pair: -pair[0])
    best = matches[0][1]

    # Two different departments both matched (e.g. a line naming several);
    # that is not a confident identification.
    distinct = {canonical for _, canonical in matches}
    if len(distinct) > 1 and matches[0][0] == matches[1][0]:
        return None
    return best
