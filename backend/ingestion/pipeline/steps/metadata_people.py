import re
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep
from ingestion.pipeline.utils.text_cleaners import (
    normalize_line,
    extract_roll,
    extract_name_from_line,
    looks_like_noise,
    split_person_title,
    NAME_WITH_TITLE,
    ROLL_PATTERN,
    SUPERVISOR_PATTERN,
    TITLE_PATTERN,
)

# A candidate name is only accepted as a supervisor once it's been split
# from any leading title -- this both validates its shape (2-4 capitalized
# words) and normalizes it, decoupled from whether it happened to carry a
# single title, a stacked one ("Prof. Dr. ..."), or none at all.
_DESIGNATION_KEYWORDS = {
    "professor", "lecturer", "examiner", "head", "dean", "coordinator",
    "co-ordinator", "department", "campus", "university",
    # Role labels. Nobody is named "Supervisor", so a line that is really a
    # signature-block label can never be mistaken for the person under it.
    "supervisor", "co-supervisor", "signature", "external", "internal",
}


class MetadataPeopleStep(BasePipelineStep):
    step_name = "People & Roles Metadata Extraction"

    @staticmethod
    def collect_front_matter_lines(pages, skip_cover=False):
        lines = []
        for page in pages[:8]:
            page_type = page.get("page_type")
            if skip_cover and page_type == "cover":
                continue
            if page_type in {"cover", "approval", "acknowledgement", "abstract", "declaration", "certificate"}:
                for line in page.get("lines", []):
                    text = normalize_line(line.get("text", ""))
                    if text:
                        lines.append(text)
        return lines

    @classmethod
    def extract_authors(cls, pages, academic_level):
        # The cover/title page is the strongest, most consistent source for
        # author names -- try it (together with the rest of the front
        # matter) first, and only fall back to scanning approval/
        # acknowledgement pages without it if that finds nothing. Lines are
        # collected in document order, so cover-page names still sort ahead
        # of anything from later pages either way.
        cover_lines = cls.collect_front_matter_lines(pages, skip_cover=False)
        authors = cls._extract_authors_from_list(cover_lines, academic_level)
        if not authors:
            inner_lines = cls.collect_front_matter_lines(pages, skip_cover=True)
            authors = cls._extract_authors_from_list(inner_lines, academic_level)
        return authors

    @staticmethod
    def _looks_like_person_name(text: str) -> bool:
        if not text or looks_like_noise(text) or extract_roll(text):
            return False
        words = text.split()
        if not (2 <= len(words) <= 4):
            return False
        return all(re.match(r"^[A-Z][a-zA-Z'.\-]*$", word) for word in words)

    @staticmethod
    def _split_multi_student_line(text):
        """A single line naming more than one student ("Aarav Shrestha
        080BCT022, Nischal Karki 079BCT047") is split into one chunk per
        student -- each chunk still has its own name and roll number
        together, so the ordinary one-student-per-line pairing logic below
        handles it unchanged. Lines with 0 or 1 roll numbers are left as-is."""
        if len(ROLL_PATTERN.findall(text)) < 2:
            return [text]
        return [chunk.strip() for chunk in re.split(r"[,;]|\band\b", text, flags=re.IGNORECASE) if chunk.strip()]

    @classmethod
    def _extract_authors_from_list(cls, lines, academic_level):
        cleaned = []
        for line in lines:
            text = normalize_line(line)
            cleaned.extend(cls._split_multi_student_line(text) if text else [text])
        authors = []
        seen = set()
        consumed_as_name = set()

        for idx, text in enumerate(cleaned):
            if not text or idx in consumed_as_name or looks_like_noise(text):
                continue
            roll = extract_roll(text)
            if not roll:
                continue

            name = extract_name_from_line(text)
            if not name or len(name.split()) < 2:
                # The roll number is alone on its own line -- the student's
                # name is most likely the immediately adjacent line, either
                # just before it ("Name" then "Roll") or just after it
                # ("Roll" then "Name"); different reports order these
                # differently, and line breaks between the two are common.
                name = None
                for neighbor_idx in (idx - 1, idx + 1):
                    if 0 <= neighbor_idx < len(cleaned) and neighbor_idx not in consumed_as_name:
                        candidate = cleaned[neighbor_idx]
                        if cls._looks_like_person_name(candidate):
                            name = candidate
                            consumed_as_name.add(neighbor_idx)
                            break

            if not name or name.lower().startswith("submitted") or len(name.split()) < 2:
                continue

            key = (name.lower(), roll.lower())
            if key in seen:
                continue
            seen.add(key)
            consumed_as_name.add(idx)
            authors.append({
                "full_name": name,
                "roll_number": roll,
                "academic_level": academic_level,
                "role": "Author",
                "display_order": len(authors) + 1,
            })
        return authors

    @staticmethod
    def _looks_like_faculty_name(candidate: str) -> bool:
        name, _ = split_person_title(candidate)
        if not name:
            return False
        words = name.split()
        if not (2 <= len(words) <= 4):
            return False
        return all(re.match(r"^[A-Z][a-zA-Z'\-]*$", word) for word in words)

    # A standalone label line naming the role next to a signature/name field
    # -- e.g. "Supervisor", "Supervisor:", "Co-Supervisor", "Name of
    # Supervisor:", "Supervisor's Signature", "Internal Examiner:". Anchored
    # both ends so it only matches a line that IS the label (not a label
    # word appearing inside a longer sentence), but tolerant of the
    # colon/possessive/"Name of"/"Signature of" decoration real signature
    # blocks commonly use -- a bare exact-string match ("Supervisor" with no
    # trailing colon) would silently miss most real approval pages, which
    # is why supervisors were going undetected even when a label was right
    # there.
    SUPERVISOR_LABEL_LINE = re.compile(
        r"^(?:name\s+of\s+(?:the\s+)?|signature\s+of\s+(?:the\s+)?)?"
        r"(?:under\s+(?:the\s+)?(?:supervision|guidance)\s+of"
        r"|supervised\s+by|guided\s+by"
        r"|(?P<role>(?:co[-\s]?)?(?:project\s+)?supervisor"
        r"|internal\s+examiner|external\s+examiner))"
        r"(?:'s\s+(?:name|signature))?"
        r"\s*:?\s*$",
        re.IGNORECASE,
    )

    # A line that STARTS a DIFFERENT committee member's signature block
    # (Project Co-ordinator, Head of Department, or a repeat of one of the
    # SUPERVISOR_LABEL_LINE roles) -- unlike that pattern, this one isn't
    # anchored to the end of the line, since the real-world failure case is
    # a role label immediately followed by other text on the SAME line
    # ("Project Co-ordinator:  Er."), not just a bare label line.
    OTHER_ROLE_LABEL_START = re.compile(
        r"^(?:name\s+of\s+(?:the\s+)?|signature\s+of\s+(?:the\s+)?)?"
        r"(?:(?:co[-\s]?)?supervisor|internal\s+examiner|external\s+examiner"
        r"|project\s+co[-\s]?ordinator|co[-\s]?ordinator|head\s+of\s+department)"
        r"\s*:",
        re.IGNORECASE,
    )

    @staticmethod
    def _label_role(role_text: str) -> str:
        role_text = role_text.lower()
        if "internal" in role_text:
            return "Internal Examiner"
        if "external" in role_text:
            return "External Examiner"
        if "co" in role_text:
            return "Co-Supervisor"
        return "Supervisor"

    @classmethod
    def _label_based_supervisors(cls, pages):
        """Highest-confidence path: an explicit "Supervisor" / "Co-Supervisor"
        label (standalone or same-line with a title-prefixed name), found on
        an approval or acknowledgement page. Handles both "label, then name
        on a following line" and "Prof. X ... Supervisor" on one line."""
        people = []
        seen_names = set()

        for page in pages:
            if page.get("page_type") not in ["cover", "approval", "acknowledgement"]:
                continue

            lines = page.get("lines", [])
            for idx, line in enumerate(lines):
                text = normalize_line(line.get("text", ""))
                if not text:
                    continue

                lowered = text.lower()

                label_match = cls.SUPERVISOR_LABEL_LINE.match(text)
                if label_match or text.startswith("...."):
                    matched_role = label_match.group("role") if label_match else None
                    role = cls._label_role(matched_role) if matched_role else "Supervisor"
                    found_for_label = 0

                    for lookahead in range(1, 7):
                        if idx + lookahead >= len(lines):
                            break
                        next_text = normalize_line(lines[idx + lookahead].get("text", ""))
                        if cls.OTHER_ROLE_LABEL_START.match(next_text):
                            # The name field for THIS role was left blank on
                            # the source PDF (a common real-world case --
                            # the signature line has no name typed in at
                            # all), and scanning has run straight into the
                            # NEXT committee member's own label/block
                            # ("Project Co-ordinator: Er."). That block
                            # belongs to a different role entirely -- give
                            # up on finding a name for this one rather than
                            # reaching past the blank into it.
                            break
                        if not next_text or next_text.startswith("....") or len(next_text.split()) > 4:
                            continue

                        cleaned_candidate = re.sub(r"^(name|:|-|\.|\s)+", "", next_text, flags=re.IGNORECASE).strip(" -.")
                        if any(kw in cleaned_candidate.lower() for kw in _DESIGNATION_KEYWORDS):
                            continue

                        # A name wrapped across two rendered lines ("Dr.
                        # Ranju Kumari" / "Shiwakoti") is rejoined before
                        # being tested, so the surname is not dropped.
                        if idx + lookahead + 1 < len(lines):
                            tail = normalize_line(lines[idx + lookahead + 1].get("text", ""))
                            if (
                                tail
                                and len(tail.split()) == 1
                                and re.match(r"^[A-Z][a-zA-Z'\-]+$", tail)
                                and tail.lower() not in _DESIGNATION_KEYWORDS
                                and not cls.OTHER_ROLE_LABEL_START.match(tail)
                                # Only when the candidate is still SHORT --
                                # "Dr. Ranju Kumari" reads as a complete
                                # name on its own, so testing that it looks
                                # invalid would never fire. Two name words
                                # followed by a lone capitalised word is the
                                # wrapped-surname shape.
                                and len(split_person_title(cleaned_candidate)[0].split()) < 3
                            ):
                                cleaned_candidate = f"{cleaned_candidate} {tail}"

                        if cls._looks_like_faculty_name(cleaned_candidate):
                            name, designation = split_person_title(cleaned_candidate)
                            if name.lower() not in seen_names:
                                if idx + lookahead + 1 < len(lines):
                                    follow_text = normalize_line(lines[idx + lookahead + 1].get("text", ""))
                                    if any(r in follow_text.lower() for r in ["professor", "lecturer", "engineer"]):
                                        designation = follow_text

                                seen_names.add(name.lower())
                                people.append({
                                    "full_name": name,
                                    "designation": designation or None,
                                    "academic_level": "Faculty",
                                    "role": role,
                                    "display_order": len(people) + 1,
                                    "confidence": 0.9,
                                    "confidence_source": "explicit_label",
                                })
                                found_for_label += 1
                                # A single label can introduce several
                                # supervisors listed one under the other;
                                # keep scanning rather than stopping at the
                                # first, but stop once the block clearly
                                # ends.
                                if found_for_label >= 3:
                                    break
                    continue

                has_prefix = TITLE_PATTERN.search(text)
                if has_prefix and ("supervisor" in lowered or "advisor" in lowered or "guided by" in lowered):
                    role = "Co-Supervisor" if "co-" in lowered or "co " in lowered else "Supervisor"
                    candidate = text
                    if ":" in text:
                        _, candidate = text.split(":", 1)

                    cleaned_candidate = re.sub(r"^(name|:|-|\.|\s)+", "", candidate, flags=re.IGNORECASE).strip(" -.")
                    if any(kw in cleaned_candidate.lower() for kw in _DESIGNATION_KEYWORDS):
                        continue

                    if cls._looks_like_faculty_name(cleaned_candidate):
                        name, designation = split_person_title(cleaned_candidate)
                        if name.lower() not in seen_names:
                            if idx + 1 < len(lines):
                                follow_text = normalize_line(lines[idx + 1].get("text", ""))
                                if any(r in follow_text.lower() for r in ["professor", "lecturer"]):
                                    designation = follow_text

                            seen_names.add(name.lower())
                            people.append({
                                "full_name": name,
                                "designation": designation or None,
                                "academic_level": "Faculty",
                                "role": role,
                                "display_order": len(people) + 1,
                                "confidence": 0.9,
                                "confidence_source": "explicit_label",
                            })
        return people

    @staticmethod
    def _joined_page_text(pages, page_types):
        """Concatenates a page's lines into one continuous string per page so
        a sentence that wraps across several extracted lines (e.g. an
        acknowledgement paragraph) can be scanned as a whole, rather than
        line-by-line. Pages are kept separate (joined by a period) so a cue
        phrase and a name can never be paired across a page boundary."""
        blocks = []
        for page in pages:
            if page.get("page_type") not in page_types:
                continue
            page_text = " ".join(
                normalize_line(line.get("text", ""))
                for line in page.get("lines", [])
                if normalize_line(line.get("text", ""))
            )
            if page_text:
                blocks.append(page_text)
        return ". ".join(blocks)

    @classmethod
    def _sentence_context_supervisors(cls, pages):
        """Lower-confidence, fallback path: a supervisor identified only
        through sentence context, e.g. "...Asst. Prof. Bikal Adhikari, who
        also serves as our supervisor..." inside acknowledgement prose, with
        no standalone "Supervisor:" label anywhere. Requires BOTH a
        supervisor cue phrase AND a title-prefixed name within a short,
        same-sentence window of each other -- a bare mention of a faculty
        member's name (e.g. as IC Chair or Head of Department) without that
        combination is never picked up here."""
        text = cls._joined_page_text(pages, {"acknowledgement", "approval"})
        if not text:
            return []

        name_matches = list(NAME_WITH_TITLE.finditer(text))
        if not name_matches:
            return []

        MAX_GAP = 150
        found = []
        seen_names = set()
        for cue in SUPERVISOR_PATTERN.finditer(text):
            role = "Co-Supervisor" if re.search(r"co[-\s]?supervisor", cue.group(0), re.IGNORECASE) else "Supervisor"

            best_match, best_distance = None, None
            for name_match in name_matches:
                if name_match.end() <= cue.start():
                    gap = text[name_match.end():cue.start()]
                    distance = cue.start() - name_match.end()
                elif name_match.start() >= cue.end():
                    gap = text[cue.end():name_match.start()]
                    distance = name_match.start() - cue.end()
                else:
                    continue  # overlapping -- the "name" is inside the cue phrase itself
                if distance > MAX_GAP or re.search(r"[.\n]", gap):
                    continue  # different sentence
                if best_distance is None or distance < best_distance:
                    best_match, best_distance = name_match, distance

            if best_match is None:
                continue

            raw_candidate = re.sub(r"\s+", " ", best_match.group(0)).strip()
            name, designation = split_person_title(raw_candidate)
            # NAME_WITH_TITLE greedily captures up to 4 trailing capitalized
            # words after a title, so it can overrun past the real name into
            # adjacent capitalized text -- a designation word right after it
            # ("...Koirala Professor") or, worse, straight into an
            # institutional phrase where EVERY word happens to be
            # capitalized ("...Adhikari Department Of Electronics"), or
            # even capture nothing but institutional text at all. Cleaned
            # up by the same shared truncation/rejection rule the
            # last-resort positional detector below also uses.
            name = " ".join(cls._truncate_at_institutional_word(name.split()))
            if not name or len(name.split()) < 2 or name.lower() in seen_names:
                continue
            seen_names.add(name.lower())
            found.append({
                "full_name": name,
                "designation": designation or None,
                "academic_level": "Faculty",
                "role": role,
                "display_order": 0,
                "confidence": 0.55,
                "confidence_source": "sentence_context",
            })
        return found

    @staticmethod
    def _truncate_at_institutional_word(name_words):
        """Shared by both fallback detectors below: rejects a captured
        "name" outright if even its presumed first/last words are
        themselves institutional text, and otherwise truncates at the
        first institutional word found from the 3rd captured word
        onward -- the same fix applied to the sentence-context detector,
        reused here since both paths can overrun into adjacent
        capitalized institutional text the same way."""
        if not name_words:
            return []
        if any(w.strip(".,").lower() in _DESIGNATION_KEYWORDS for w in name_words[:2]):
            return []
        for idx in range(2, len(name_words)):
            if name_words[idx].strip(".,").lower() in _DESIGNATION_KEYWORDS:
                return name_words[:idx]
        return name_words

    @classmethod
    def _positional_last_resort_supervisor(cls, pages):
        """Absolute last resort, tried only when nothing else found
        anything for the whole document. Many approval pages list a
        supervisor's name and designation with no explicit "Supervisor"
        label or cue phrase at all -- just a name, then a title/
        designation line, in a signature block (by long-standing
        convention: the supervisor's signature line is listed first,
        ahead of the alphabetically-ordered rest of the examining
        committee). Some acknowledgements simply thank a titled person by
        name with no "supervisor"/"guided by"/"advisor" wording attached
        at all either. Both patterns are captured here, always at the
        lowest confidence in this pipeline, so they surface for review
        rather than being silently trusted the way an explicit-label or
        cue-phrase match is."""
        # 1) A name line immediately followed (within a couple of lines)
        #    by a designation line, on an approval/acknowledgement page.
        for page in pages:
            if page.get("page_type") not in ["approval", "acknowledgement"]:
                continue
            lines = page.get("lines", [])
            for idx, line in enumerate(lines):
                text = normalize_line(line.get("text", ""))
                if not text or not cls._looks_like_faculty_name(text):
                    continue
                # _looks_like_faculty_name only checks capitalized-word
                # SHAPE, which a fully upper-case page heading like
                # "CERTIFICATE OF APPROVAL" also satisfies -- with no
                # explicit label to anchor on (this is the un-gated
                # last-resort path), that shape check alone isn't enough.
                # A real name in one of these signature blocks is
                # essentially never rendered fully upper-case, even when
                # the page's own heading is.
                if text.isupper():
                    continue
                name, designation = split_person_title(text)
                if not name:
                    continue
                # This path has no label and no cue phrase to anchor on, so
                # a signature-block ROLE LABEL ("External Examiner",
                # "Project Co-ordinator") satisfies the capitalized-words
                # shape test just as a real name does -- and the very next
                # line is usually a designation, which used to complete the
                # match and store the label itself as the supervisor's name.
                # The same institutional-word rule the other fallbacks use
                # rejects it here too.
                name_words = cls._truncate_at_institutional_word(name.split())
                if len(name_words) < 2:
                    continue
                name = " ".join(name_words)
                if not designation:
                    for lookahead in (1, 2):
                        if idx + lookahead >= len(lines):
                            break
                        next_text = normalize_line(lines[idx + lookahead].get("text", ""))
                        if any(r in next_text.lower() for r in ["professor", "lecturer", "reader", "instructor"]):
                            designation = next_text
                            break
                if not designation:
                    continue
                return [{
                    "full_name": name,
                    "designation": designation,
                    "academic_level": "Faculty",
                    "role": "Supervisor",
                    "display_order": 1,
                    "confidence": 0.5,
                    "confidence_source": "positional_name_and_designation",
                }]

        # 2) No name+designation pair found either -- fall back to the
        #    first titled person named anywhere in the acknowledgement/
        #    approval text, with no cue phrase required at all. The
        #    weakest evidence used anywhere in this pipeline.
        text = cls._joined_page_text(pages, {"acknowledgement", "approval"})
        match = NAME_WITH_TITLE.search(text)
        if match:
            raw_candidate = re.sub(r"\s+", " ", match.group(0)).strip()
            name, designation = split_person_title(raw_candidate)
            name_words = cls._truncate_at_institutional_word(name.split())
            name = " ".join(name_words)
            if name and len(name_words) >= 2:
                return [{
                    "full_name": name,
                    "designation": designation or None,
                    "academic_level": "Faculty",
                    "role": "Supervisor",
                    "display_order": 1,
                    "confidence": 0.4,
                    "confidence_source": "positional_first_named_in_acknowledgement",
                }]

        return []

    @classmethod
    def extract_supervisors(cls, pages):
        people = cls._label_based_supervisors(pages)
        seen_names = {p["full_name"].lower() for p in people}

        # The contextual detector only fills in names the stronger,
        # explicit-label detector didn't already find -- explicit evidence
        # always wins over a sentence-context guess.
        for candidate in cls._sentence_context_supervisors(pages):
            if candidate["full_name"].lower() in seen_names:
                continue
            seen_names.add(candidate["full_name"].lower())
            candidate["display_order"] = len(people) + 1
            people.append(candidate)

        # Only reached when NEITHER an explicit label NOR a supervisor cue
        # phrase found anything at all for this document -- without this,
        # a document that only ever names its supervisor via a bare
        # signature block or an unattached acknowledgement mention
        # produced no supervisor whatsoever.
        if not people:
            people = cls._positional_last_resort_supervisor(pages)

        return people

    @staticmethod
    def _batch_from_roll_number(authors):
        """A roll number's first 3 digits are the actual admission batch
        code (e.g. "078BCT083" -> "078") -- a far more direct and reliable
        source than scanning cover-page text for a mentioned year, and it
        naturally survives even when the cover page never states a batch
        explicitly at all. Author roll numbers are already normalized (no
        campus prefix, uppercased) by extract_roll/clean_roll_number at
        the point they were extracted, so no re-cleaning is needed here."""
        for author in authors:
            roll = author.get("roll_number") or ""
            if re.match(r"^\d{3}", roll):
                return roll[:3]
        return None

    def run(self, job: IngestionJob, context: dict) -> dict:
        pages = context.get("classified_pages", [])
        academic_level = context.get("academic_level", "UG")
        authors = self.extract_authors(pages, academic_level)
        supervisors = self.extract_supervisors(pages)

        draft = context.get("draft_metadata", {})
        draft["people_and_roles"] = authors + supervisors
        if "project_fields" in draft:
            draft["project_fields"]["supervisors"] = supervisors if supervisors else None
            if not draft["project_fields"].get("batch"):
                roll_batch = self._batch_from_roll_number(authors)
                if roll_batch:
                    draft["project_fields"]["batch"] = roll_batch

        context["draft_metadata"] = draft
        self.log(job, f"Extracted {len(authors)} author(s) and {len(supervisors)} supervisor(s).")
        return context
