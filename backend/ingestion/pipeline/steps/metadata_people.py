import re
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep
from ingestion.pipeline.utils.text_cleaners import (
    normalize_line,
    extract_roll,
    extract_name_from_line,
    looks_like_noise,
    TITLE_PATTERN,
)


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
        inner_lines = cls.collect_front_matter_lines(pages, skip_cover=True)
        authors = cls._extract_authors_from_list(inner_lines, academic_level)
        if not authors:
            cover_lines = cls.collect_front_matter_lines(pages, skip_cover=False)
            authors = cls._extract_authors_from_list(cover_lines, academic_level)
        return authors

    @staticmethod
    def _extract_authors_from_list(lines, academic_level):
        authors = []
        seen = set()
        for line in lines:
            text = normalize_line(line)
            if not text or looks_like_noise(text):
                continue
            roll = extract_roll(text)
            if roll:
                name = extract_name_from_line(text)
                if name and not name.lower().startswith("submitted") and len(name.split()) >= 2:
                    key = (name.lower(), roll.lower())
                    if key not in seen:
                        seen.add(key)
                        authors.append({
                            "full_name": name,
                            "roll_number": roll,
                            "academic_level": academic_level,
                            "role": "Author",
                            "display_order": len(authors) + 1,
                        })
        return authors[:4]

    @staticmethod
    def extract_supervisors(pages):
        people = []
        seen_names = set()

        VALID_NAME_PATTERN = re.compile(
            r"^(?:(?:Prof|Dr|Mr|Mrs|Ms|Assoc\.\s*Prof|Asst\.\s*Prof)\.?\s+)?[A-Z][a-z\']+(?:\s+[A-Z][a-z\']+)+$"
        )
        DESIGNATION_KEYWORDS = {"professor", "lecturer", "examiner", "head", "dean", "coordinator", "department", "campus", "university"}

        for page in pages:
            if page.get("page_type") not in ["approval", "acknowledgement"]:
                continue

            lines = page.get("lines", [])
            for idx, line in enumerate(lines):
                text = normalize_line(line.get("text", ""))
                if not text:
                    continue

                lowered = text.lower()

                if lowered in ["supervisor", "co-supervisor", "internal examiner", "external examiner"] or text.startswith("...."):
                    role = "Co-Supervisor" if "co-" in lowered else "Supervisor"

                    for lookahead in range(1, 4):
                        if idx + lookahead >= len(lines):
                            break
                        next_text = normalize_line(lines[idx + lookahead].get("text", ""))
                        if not next_text or next_text.startswith("....") or len(next_text.split()) > 4:
                            continue

                        cleaned_candidate = re.sub(r"^(name|:|-|\.|\s)+", "", next_text, flags=re.IGNORECASE).strip(" -.")
                        if any(kw in cleaned_candidate.lower() for kw in DESIGNATION_KEYWORDS):
                            continue

                        if VALID_NAME_PATTERN.match(cleaned_candidate):
                            if cleaned_candidate.lower() not in seen_names:
                                designation = None
                                has_prefix = TITLE_PATTERN.search(cleaned_candidate)
                                if has_prefix:
                                    designation = has_prefix.group(0).strip()

                                if idx + lookahead + 1 < len(lines):
                                    follow_text = normalize_line(lines[idx + lookahead + 1].get("text", ""))
                                    if any(r in follow_text.lower() for r in ["professor", "lecturer", "engineer"]):
                                        designation = follow_text

                                seen_names.add(cleaned_candidate.lower())
                                people.append({
                                    "full_name": cleaned_candidate,
                                    "designation": designation,
                                    "academic_level": "Faculty",
                                    "role": role,
                                    "display_order": len(people) + 1,
                                })
                                break
                    continue

                has_prefix = TITLE_PATTERN.search(text)
                if has_prefix and ("supervisor" in lowered or "advisor" in lowered or "guided by" in lowered):
                    role = "Co-Supervisor" if "co-" in lowered or "co " in lowered else "Supervisor"
                    name = text
                    if ":" in text:
                        _, name = text.split(":", 1)

                    cleaned_name = re.sub(r"^(name|:|-|\.|\s)+", "", name, flags=re.IGNORECASE).strip(" -.")
                    if any(kw in cleaned_name.lower() for kw in DESIGNATION_KEYWORDS):
                        continue

                    if VALID_NAME_PATTERN.match(cleaned_name) and cleaned_name.lower() not in seen_names:
                        designation = has_prefix.group(0).strip()
                        if idx + 1 < len(lines):
                            follow_text = normalize_line(lines[idx + 1].get("text", ""))
                            if any(r in follow_text.lower() for r in ["professor", "lecturer"]):
                                designation = follow_text

                        seen_names.add(cleaned_name.lower())
                        people.append({
                            "full_name": cleaned_name,
                            "designation": designation,
                            "academic_level": "Faculty",
                            "role": role,
                            "display_order": len(people) + 1,
                        })
        return people

    def run(self, job: IngestionJob, context: dict) -> dict:
        pages = context.get("classified_pages", [])
        academic_level = context.get("academic_level", "UG")
        authors = self.extract_authors(pages, academic_level)
        supervisors = self.extract_supervisors(pages)

        draft = context.get("draft_metadata", {})
        draft["people_and_roles"] = authors + supervisors
        if "project_fields" in draft:
            draft["project_fields"]["supervisors"] = supervisors if supervisors else None

        context["draft_metadata"] = draft
        self.log(job, f"Extracted {len(authors)} author(s) and {len(supervisors)} supervisor(s).")
        return context
