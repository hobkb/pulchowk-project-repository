import re
from rapidfuzz.process import extractOne
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep
from ingestion.pipeline.utils.text_cleaners import (
    normalize_line,
    YEAR_PATTERN,
    REPOSITORY_URL_PATTERN,
)


class MetadataFrontMatterStep(BasePipelineStep):
    step_name = "Front Matter Metadata Extraction"

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

    @staticmethod
    def extract_batch(lines):
        for line in lines[:12]:
            matches = YEAR_PATTERN.findall(line)
            if matches:
                for match in matches:
                    year = int(match)
                    if 1900 <= year <= 2100:
                        return str(year)
        return None

    @staticmethod
    def extract_campus_and_department(lines):
        campus = None
        department = None
        for line in lines:
            text = normalize_line(line)
            if not text:
                continue
            lowered = text.lower()
            if not campus and "campus" in lowered:
                campus = text
            if not department and "department" in lowered:
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

    @staticmethod
    def extract_clean_project_title(cover_text):
        if not cover_text:
            return None
        lines = [normalize_line(line) for line in cover_text.splitlines() if normalize_line(line)]
        candidates = []
        for line in lines:
            lowered = line.lower()
            if len(line.split()) < 2 or len(line.split()) > 12:
                continue
            if any(token in lowered for token in [
                "department", "submitted", "campus", "supervisor", "abstract",
                "approval", "thesis", "report", "github", "roll", "student",
                "committee", "tribhuvan", "tribhuwan", "university", "institute",
                "faculty", "engineering", "bachelor", "master", "doctor",
            ]):
                continue

            if re.match(r"^\d{4}$", line):
                continue
            candidates.append(line)
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
        cover_lines = [line.get("text", "") for line in cover_page.get("lines", [])] if cover_page else []
        front_matter_lines = self.collect_front_matter_lines(pages, skip_cover=False)

        abstract_text, keywords = self.extract_abstract_and_keywords(pages)
        academic_level = self.extract_academic_level(cover_lines)
        project_type = self.extract_project_type(cover_lines)
        batch = self.extract_batch(cover_lines)
        campus_name, department_name = self.extract_campus_and_department(cover_lines)
        research_group_name = self.extract_research_group(pages)
        title = self.extract_clean_project_title("\n".join(front_matter_lines))
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
