import re
from rapidfuzz.process import extractOne
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep
from organization.departments import canonical_department
from ingestion.pipeline.utils.text_cleaners import (
    normalize_line,
    REPOSITORY_URL_PATTERN,
)


class MetadataFrontMatterStep(BasePipelineStep):
    step_name = "Front Matter Metadata Extraction"

    # An explicit 3-digit batch mention ("Batch: 078", "078 Batch") -- the
    # format this system actually uses everywhere else (the batch dropdown,
    # roll-number prefixes, "Batch 078" display text on project pages).
    BATCH_CODE_PATTERN = re.compile(r"\bbatch\b\s*[:\-]?\s*(\d{3})\b|\b(\d{3})\s*batch\b", re.IGNORECASE)

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

    @staticmethod
    def extract_project_type(lines):
        text = " ".join(normalize_line(line) for line in lines).lower()
        if "thesis" in text:
            return "Thesis"
        if "faculty project" in text or ("faculty" in text and "project" in text):
            return "Faculty Project"
        if "research" in text:
            return "Research"
        if "minor" in text:
            return "Minor"
        return "Major"

    @staticmethod
    def extract_academic_level(lines):
        text = " ".join(normalize_line(line) for line in lines).lower()
        if "phd" in text or "doctor" in text:
            return "PhD"
        if "masters" in text or "master" in text:
            return "Masters"
        if "faculty" in text:
            return "Faculty"
        return "UG"

    @classmethod
    def extract_batch(cls, lines):
        """Looks for an explicit 3-digit batch code mention. A bare 4-digit
        calendar year on the cover page (the previous approach here) isn't
        a reliable substitute: it's usually the submission/defense year,
        several years after the actual admission batch, in an entirely
        different format from what the rest of the system expects. When no
        explicit mention exists, MetadataPeopleStep fills this in
        afterward from a student author's roll number, which encodes the
        real admission batch directly (e.g. "078BCT083" -> "078")."""
        for line in lines[:20]:
            m = cls.BATCH_CODE_PATTERN.search(line)
            if m:
                return m.group(1) or m.group(2)
        return None

    @staticmethod
    def extract_campus_and_department(lines, title=None):
        # A title that itself contains the word "campus" or "department"
        # (a real, legitimate case -- e.g. a campus-themed project) must
        # not win this scan just for appearing earlier in reading order
        # than the actual institutional declaration line, and a genuine
        # campus/department line is short (an address-style label, not a
        # long title sentence) -- both checks target the same underlying
        # problem: keyword matching alone can't distinguish "this line
        # mentions campus" from "this line IS the campus declaration".
        title_lower = (title or "").strip().lower()
        campus = None
        department = None
        for line in lines:
            text = normalize_line(line)
            if not text or text.lower() == title_lower:
                continue
            lowered = text.lower()
            if not campus and "campus" in lowered and len(text.split()) <= 8:
                campus = text
            if not department and "department" in lowered and len(text.split()) <= 12:
                department = text
        return campus, department

    @staticmethod
    def extract_abstract_and_keywords(pages):
        abstract_lines = []
        raw_keyword_block = []
        in_keyword_zone = False

        for page in pages:
            if page.get("page_type") != "abstract":
                continue
            for line in page.get("lines", []):
                text = normalize_line(line.get("text", ""))
                if not text:
                    continue
                lowered = text.lower()

                if lowered.startswith("keywords") or lowered.startswith("keyword"):
                    in_keyword_zone = True
                    raw_keyword_block.append(text)
                    continue

                if in_keyword_zone:
                    if len(text.split()) < 5 or "," in text or ";" in text or "•" in text or text.endswith("-"):
                        raw_keyword_block.append(text)
                    else:
                        in_keyword_zone = False
                    continue

                if lowered == "abstract":
                    continue
                abstract_lines.append(text)

        abstract_text = "\n".join(abstract_lines).strip()
        keywords = []

        combined_keywords_text = " ".join(raw_keyword_block)
        if ":" in combined_keywords_text:
            _, combined_keywords_text = combined_keywords_text.split(":", 1)

        combined_keywords_text = re.sub(r"^(keywords?|keyword)\s*", "", combined_keywords_text, flags=re.IGNORECASE).strip(" :-")
        combined_keywords_text = re.sub(r"(\w+)-\s+(\w+)", r"\1\2", combined_keywords_text)

        for item in re.split(r"[,;•·]|\band\b", combined_keywords_text):
            item = item.strip().strip(".-")
            item = re.sub(r"\s+[b-z]\b$", "", item).strip()
            if item and len(item.split()) <= 4:
                keywords.append(item)

        return abstract_text, keywords

    @staticmethod
    def extract_research_group(pages):
        canonical_groups = [
            "Information and Communication Research Lab",
            "Embedded Systems and Robotics Lab",
            "Software Engineering Research Lab",
            "Network Security Research Lab",
            "AI and Data Science Lab",
        ]
        text_blocks = []
        for page in pages[:6]:
            for line in page.get("lines", []):
                text_blocks.append(normalize_line(line.get("text", "")))
        combined = "\n".join(text_blocks)
        if not combined:
            return None
        best_match = extractOne(combined, canonical_groups, score_cutoff=60)
        if best_match:
            return best_match[0]
        return None

    _TITLE_EXCLUDE_TOKENS = [
        "department", "submitted", "campus", "supervisor", "abstract",
        "approval", "thesis", "report", "github", "roll", "student",
        "committee", "tribhuvan", "tribhuwan", "university", "institute",
        "faculty", "engineering", "bachelor", "master", "doctor",
        "proposal", "mid-term", "midterm", "fulfillment", "fulfilment",
    ]

    @classmethod
    def _is_probable_title_line(cls, line: str) -> bool:
        words = line.split()
        if len(words) < 2 or len(words) > 14:
            return False
        lowered = line.lower()
        if any(token in lowered for token in cls._TITLE_EXCLUDE_TOKENS):
            return False
        if re.match(r"^\d{4}$", line):
            return False
        return True

    @staticmethod
    def _is_plausible_title_fragment(text: str) -> bool:
        """A much lighter check than _is_probable_title_line: this is
        applied to individual PHYSICAL LINES of a title that may span
        several of them ("SMART CAMPUS ENERGY" / "MONITORING AND ANOMALY" /
        "DETECTION SYSTEM"), so it deliberately does NOT keyword-blacklist
        institutional words like "campus" or "engineering" -- those are
        exactly the kind of word a real project title can legitimately
        contain, and once font size + layout block already isolate the
        title from the surrounding institution/author text, a keyword
        blacklist only introduces false negatives like dropping "SMART
        CAMPUS ENERGY" for containing "campus". Only rules out lines that
        clearly cannot be part of any title at all."""
        if len(text) > 120:
            return False
        if re.match(r"^\d{4}$", text):
            return False
        return True

    # Nepali IOE/Pulchowk cover pages overwhelmingly follow one fixed
    # template: "A [FINAL YEAR/MINOR/MAJOR] PROJECT REPORT ON" (sometimes
    # split across separate lines, with "ON" on its own line), immediately
    # followed by the actual project title, then "SUBMITTED BY:"/author
    # names/roll numbers. This marker is a far more reliable title anchor
    # than font-size guessing for this template family: the institution
    # name ("TRIBHUVAN UNIVERSITY"), "A", "PROJECT REPORT", and "ON" are
    # routinely rendered in the SAME largest font as the real title (and
    # sometimes even the same layout block), which is exactly what caused
    # font-size-tier extraction to pick "TRIBHUVAN UNIVERSITY" or "A
    # Project Report" as the title instead of the actual project name.
    # The report marker as real covers write it: "A Major Project Final
    # Report", "Minor Project Report", "Final Report", "A Thesis", with the
    # qualifiers in any combination and "On" either appended or on its own
    # line beneath.
    _REPORT_MARKER_BODY = (
        r"(?:A|AN)?\s*"
        r"(?:FINAL\s+YEAR\s+|MINOR\s+|MAJOR\s+)?"
        r"(?:PROJECT\s+)?"
        r"(?:FINAL\s+)?"
        r"(?:REPORT|PROJECT|THESIS|DISSERTATION|PROJECT\s+REPORT)"
    )
    _REPORT_WORD = re.compile(rf"^{_REPORT_MARKER_BODY}\s*$", re.IGNORECASE)
    _REPORT_WORD_WITH_ON = re.compile(
        rf"^{_REPORT_MARKER_BODY}\s+ON\s*$", re.IGNORECASE
    )
    _BARE_ON = re.compile(r"^ON\s*$", re.IGNORECASE)

    # Everything a cover page prints AROUND the title. Matched anywhere in a
    # line, not just at its start: real covers frequently run the title and
    # the next boilerplate phrase together into one rendered line ("... FOR
    # PULCHOWK CAMPUS SUBMITTED BY"), and an anchored match let all of that
    # through into the stored title.
    _SCAFFOLD_PHRASE = re.compile(
        r"("
        r"submitted\b|"
        r"under\s+the\s+(?:supervision|guidance)|supervised\s+by|"
        r"in\s+partial\s+fulfil(?:l)?ment|as\s+partial\s+fulfil(?:l)?ment|"
        r"in\s+fulfil(?:l)?ment|"
        r"for\s+the\s+(?:partial\s+)?(?:degree|award)|"
        r"bachelor(?:'?s)?\s+(?:of|in|degree)|master(?:'?s)?\s+(?:of|in|degree)|"
        r"doctor\s+of|degree\s+of|"
        r"tribhuvan\s+universit|tribhuwan\s+universit|"
        r"institute\s+of\s+engineering|pulchowk\s+campus|"
        r"department\s+of\s+(?:electronics|computer|civil|mechanical|electrical|applied)|"
        r"a\s+(?:major|minor|final\s+year)?\s*project\s+report|"
        r"project\s+report\s+on"
        r")",
        re.IGNORECASE,
    )
    _TITLE_TERMINATOR = _SCAFFOLD_PHRASE
    _ROLL_NUMBER_FRAGMENT = re.compile(r"\d{3}[a-zA-Z]{2,5}\d{2,4}")

    # "Submitted By" / "Submitted To" and friends, used to locate the
    # author block on a cover page.
    _AUTHOR_BLOCK_MARKER = re.compile(
        r"^\s*(?:submitted\s+(?:by|to)|prepared\s+by|by)\s*[:\-]?\s*$",
        re.IGNORECASE,
    )

    @classmethod
    def _is_inside_author_block(cls, texts, index):
        """True when the line at `index` sits in the cover's author block.

        Decided from STRUCTURE, not from what the words look like: a title
        and a person's name are both short runs of capitalised words, so no
        vocabulary test can separate them reliably. What does separate them
        is context -- an author's name is introduced by a "Submitted By"
        marker and/or sits beside a roll number.
        """
        # A roll number on the same line, or on either neighbouring line.
        for offset in (0, 1, -1):
            neighbour = index + offset
            if 0 <= neighbour < len(texts) and cls._ROLL_NUMBER_FRAGMENT.search(texts[neighbour]):
                return True

        # A "Submitted By"-style marker within the preceding few lines,
        # with nothing but names between it and here.
        for back in range(index - 1, max(-1, index - 4), -1):
            if cls._AUTHOR_BLOCK_MARKER.match(texts[back]):
                return True
        return False

    @classmethod
    def _trim_scaffolding(cls, text):
        """Cuts a candidate title line at the first cover-page boilerplate
        phrase it runs into, and returns "" when the line is nothing but
        boilerplate. Applied to every title candidate from every path so
        no route can store "…FOR PULCHOWK CAMPUS SUBMITTED BY" as a title."""
        if not text:
            return ""
        match = cls._SCAFFOLD_PHRASE.search(text)
        if match:
            text = text[: match.start()]
        # A trailing connector left behind by the cut ("... SYSTEM FOR")
        # is not part of the title either.
        text = re.sub(
            r"\s+(?:for|by|to|of|on|in|a|an|the|and|with)\s*$", "", text.strip(), flags=re.IGNORECASE
        )
        text = text.strip(" ,:;-–—").strip()
        # A wrapped cover can leave a lone connector on its own line ("BY"
        # under "...SUBMITTED"); that is boilerplate, not a title fragment.
        if re.fullmatch(r"(?:for|by|to|of|on|in|a|an|the|and|with)", text, re.IGNORECASE):
            return ""
        return text

    @classmethod
    def _extract_title_from_marker(cls, cover_lines):
        """Finds the "...PROJECT REPORT ON" cover-page marker (however it's
        split across lines) and returns whatever title text immediately
        follows it, stopping at the first line that looks like the
        "SUBMITTED BY" block or an author's roll number rather than more
        of the title. Returns None (falling through to the layout-based
        heuristic) when the marker isn't present at all -- not every
        report uses this exact template."""
        texts = [normalize_line(line.get("text", "")) for line in cover_lines]
        texts = [t for t in texts if t]

        start = None
        for i, text in enumerate(texts):
            if cls._REPORT_WORD_WITH_ON.match(text):
                start = i + 1
                break
            if cls._REPORT_WORD.match(text) and i + 1 < len(texts) and cls._BARE_ON.match(texts[i + 1]):
                start = i + 2
                break
        if start is None:
            return None

        title_parts = []
        for offset, text in enumerate(texts[start:start + 6]):
            if cls._ROLL_NUMBER_FRAGMENT.search(text):
                break
            if not cls._is_plausible_title_fragment(text):
                break
            trimmed = cls._trim_scaffolding(text)
            if not trimmed:
                # The line was entirely boilerplate: the title has ended.
                break
            if not title_parts and cls._is_inside_author_block(texts, start + offset):
                # The marker was followed straight by the author block, so
                # this cover has no title where one was expected. Better to
                # resolve nothing than to publish a student's name as the
                # project title.
                return None
            title_parts.append(trimmed)
            if trimmed != text:
                # Boilerplate began mid-line, so the title ends here too.
                break
            if len(title_parts) >= 4:
                break

        if not title_parts:
            return None
        candidate = " ".join(title_parts).strip()
        # One stray word left after trimming is not a title -- returning
        # None lets the layout path try, rather than storing a fragment.
        return candidate if len(candidate.split()) >= 2 else None

    @classmethod
    def _extract_title_from_layout(cls, cover_lines):
        """Uses the font-size and layout-block information PDFExtractionStep
        already captured (and which used to be discarded before title
        extraction ever ran) to find the title as it actually appears: the
        run of consecutive lines, in the document's own largest cover-page
        font, that PyMuPDF grouped into one layout block. A title spanning
        several rendered lines ("AI-BASED UNDERGRADUATE PROJECT" /
        "DISCOVERY AND KNOWLEDGE" / "RETRIEVAL PLATFORM") is one such block
        and is merged into a single string instead of returning only its
        first physical line. Block-number grouping (not keyword matching)
        is what keeps a separate, smaller "Department of..." / "Submitted
        By:" block from being pulled in -- each insert_textbox-style block
        on a real cover page is already its own distinct layout block."""
        # The cover's full line order, so each candidate can be told whether
        # it sits inside the author block.
        all_texts = [normalize_line(line.get("text", "")) for line in cover_lines]

        candidates = []
        for line_index, line in enumerate(cover_lines):
            text = all_texts[line_index]
            if not text or not cls._is_plausible_title_fragment(text):
                continue
            try:
                font_size = float(line.get("font_size") or 0)
            except (TypeError, ValueError):
                font_size = 0.0
            if font_size <= 0:
                continue
            candidates.append({
                "text": text,
                "font_size": font_size,
                "block_number": line.get("block_number"),
                "author_block": cls._is_inside_author_block(all_texts, line_index),
            })

        if not candidates:
            return None

        max_font = max(c["font_size"] for c in candidates)
        tier = [c for c in candidates if c["font_size"] >= max_font - 1.0]

        best_run, current_run = [], []
        for c in tier:
            if current_run and c["block_number"] == current_run[-1]["block_number"]:
                current_run.append(c)
            else:
                if len(current_run) > len(best_run):
                    best_run = current_run
                current_run = [c]
        if len(current_run) > len(best_run):
            best_run = current_run

        if not best_run:
            return None

        # The largest-font block on a cover regularly contains the title AND
        # the line beneath it ("... SUBMITTED BY"); trim at the boilerplate
        # and drop any fragment that is purely boilerplate.
        parts = []
        for c in best_run:
            # An author's roll number is never part of the title; when the
            # largest-font block runs on into the author list, the title
            # ends here. The marker path already stopped on this.
            if cls._ROLL_NUMBER_FRAGMENT.search(c["text"]):
                break
            trimmed = cls._trim_scaffolding(c["text"])
            if not trimmed:
                if parts:
                    break
                continue
            if not parts and c.get("author_block"):
                # The largest text on the page sits in the author block, so
                # it is a student's name rather than the title.
                continue
            parts.append(trimmed)
            if trimmed != c["text"]:
                break

        return " ".join(parts) if parts else None

    @classmethod
    def extract_clean_project_title(cls, cover_text):
        """Fallback used when the cover page has no clear largest-font run
        (e.g. a scanned/flattened cover, or a title with no font-size lift
        over surrounding text) -- scans a flattened pool of front-matter
        text for a plausible single-line title. Loses multi-line titles by
        construction, which is exactly why the layout-aware path above is
        tried first."""
        if not cover_text:
            return None
        lines = [normalize_line(line) for line in cover_text.splitlines() if normalize_line(line)]

        candidates = []
        for line in lines:
            if not cls._is_probable_title_line(line):
                continue
            # This last-resort path scans flattened front matter, so it sees
            # far more boilerplate than the cover-page paths do; it needs the
            # same trimming, plus a roll-number reject, or it returns an
            # author block or a degree statement as the title.
            trimmed = cls._trim_scaffolding(line)
            if not trimmed or len(trimmed.split()) < 2:
                continue
            if cls._ROLL_NUMBER_FRAGMENT.search(trimmed):
                continue
            candidates.append(trimmed)

        if not candidates:
            return None
        for line in candidates:
            if line.isupper() or line.istitle() or len(line.split()) <= 8:
                return line
        return candidates[0]

    @staticmethod
    def extract_repository_url(pages):
        for page in pages:
            for line in page.get("lines", []):
                text = normalize_line(line.get("text", ""))
                if not text:
                    continue
                match = REPOSITORY_URL_PATTERN.search(text)
                if match:
                    return match.group(0)
        return None

    def run(self, job: IngestionJob, context: dict) -> dict:
        pages = context.get("classified_pages", [])
        cover_page = next((page for page in pages if page.get("page_type") == "cover"), None)
        cover_page_lines_raw = cover_page.get("lines", []) if cover_page else []
        cover_lines = [line.get("text", "") for line in cover_page_lines_raw]
        front_matter_lines = self.collect_front_matter_lines(pages, skip_cover=False)

        abstract_text, keywords = self.extract_abstract_and_keywords(pages)
        academic_level = self.extract_academic_level(cover_lines)
        project_type = self.extract_project_type(cover_lines)
        batch = self.extract_batch(cover_lines)
        research_group_name = self.extract_research_group(pages)
        # The "...PROJECT REPORT ON <title>" marker is tried first -- for
        # this report template it's a far more reliable anchor than font
        # size (see _extract_title_from_marker). The cover page's own
        # typography is the next fallback -- it correctly merges a
        # multi-line title instead of returning only its first rendered
        # line. Only falls back further to the flattened front-matter scan
        # when neither of those find anything to work with.
        title = self._extract_title_from_marker(cover_page_lines_raw) or \
            self._extract_title_from_layout(cover_page_lines_raw) or \
            self.extract_clean_project_title("\n".join(front_matter_lines))
        # Computed after the title so a title line that happens to contain
        # "campus"/"department" (a legitimate word choice, not necessarily
        # the institutional declaration line) can be excluded.
        campus_name, department_name = self.extract_campus_and_department(cover_lines, title=title)
        # Map whatever the cover page says ("DOECE", "Dept. of Electronics &
        # Computer Engg.") onto one of the six real departments. When it
        # cannot be identified confidently the raw text is dropped rather
        # than carried forward, so the reviewer is asked to choose instead
        # of being shown a value that would not resolve on publish.
        department_name = canonical_department(department_name)
        repository_url = self.extract_repository_url(pages)

        draft = context.get("draft_metadata", {})
        if "project_fields" not in draft:
            draft["project_fields"] = {}

        draft["project_fields"].update({
            "title": title,
            "abstract": abstract_text,
            "project_type": project_type,
            "academic_level": academic_level,
            "batch": batch,
            "campus_name": campus_name,
            "department_name": department_name,
            "research_group_name": research_group_name,
            "repository_url": repository_url,
            "status": "Review Required",
        })
        draft["keywords"] = keywords

        context["draft_metadata"] = draft
        context["academic_level"] = academic_level
        self.log(job, f"Front matter metadata extracted (Title: '{title}').")
        return context
