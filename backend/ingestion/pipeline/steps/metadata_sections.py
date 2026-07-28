import re
import time
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep
from ingestion.pipeline.utils.heading_utils import looks_like_heading
from ingestion.pipeline.utils.text_cleaners import (
    normalize_line,
    HEADING_PATTERN,
    TOC_ENTRY,
    canonicalize_heading,
)


class MetadataSectionsStep(BasePipelineStep):
    step_name = "Sections & Back Matter Extraction"

    @staticmethod
    def parse_section_heading(line_dict, active_major_chapter=0):
        if not isinstance(line_dict, dict):
            return None

        text = normalize_line(line_dict.get("text", ""))
        is_bold = bool(line_dict.get("is_bold", False))
        font_size = float(line_dict.get("font_size", 10.0))

        if not text:
            return None

        if re.match(r"^(contents?|table|figure|fig\.|index|list\s+of)", text, re.IGNORECASE):
            return None
        if TOC_ENTRY.search(text) or ". . ." in text or text.count('.') > 5:
            return None

        heading_match = HEADING_PATTERN.match(text)
        if not heading_match:
            return None

        order = heading_match.group("order")
        title = heading_match.group("title").strip()

        if not title or len(title.split()) > 10:
            return None

        try:
            seq_steps = [int(x) for x in order.split('.')]
        except ValueError:
            return None

        level = len(seq_steps)

        if level == 1:
            if font_size <= 11.5 and not is_bold:
                return None
            if seq_steps[0] != active_major_chapter + 1:
                return None
        else:
            if seq_steps[0] != active_major_chapter:
                return None

        if not is_bold and not looks_like_heading(title):
            return None

        return order, title

    @classmethod
    def extract_project_sections(cls, pages):
        section_nodes = []
        active_sections = []
        active_major_chapter = 0
        in_back_matter = False

        ignored_page_types = {
            "abstract", "acknowledgement", "approval", "cover", "copyright",
            "toc", "declaration", "certificate", "list_of_figures",
            "list_of_tables", "list_of_abbreviations",
        }

        for page in pages:
            page_type = page.get("page_type")
            page_num = page.get("page_number", page.get("page_num", 1))

            if page_type in ignored_page_types:
                active_sections = []
                continue

            for line in page.get("lines", []):
                text = normalize_line(line.get("text", ""))
                if not text or TOC_ENTRY.search(text):
                    continue
                if text.lower() == "references":
                    active_sections = []
                    in_back_matter = True
                    continue
                if in_back_matter:
                    continue

                heading_data = cls.parse_section_heading(line, active_major_chapter)

                if heading_data:
                    order, title = heading_data
                    level = len(order.split("."))

                    if level == 1:
                        active_major_chapter = int(order.split(".")[0])

                    while active_sections and active_sections[-1]["heading_level"] >= level:
                        active_sections.pop()

                    parent = active_sections[-1] if active_sections else None
                    current = {
                        "heading": f"{order} {title}",
                        "canonical_section": canonicalize_heading(title),
                        "heading_level": level,
                        "display_order": len(section_nodes) + 1,
                        "page_start": page_num,
                        "page_end": page_num,
                        "content": "",
                        "children": [],
                    }
                    if parent is not None:
                        parent["children"].append(current)
                    section_nodes.append(current)
                    active_sections.append(current)
                    continue

                if active_sections:
                    current = active_sections[-1]
                    if current["content"]:
                        current["content"] += "\n"
                    current["content"] += text
                    for section in active_sections:
                        section["page_end"] = page_num

        for section in section_nodes:
            section["word_count"] = len(re.findall(r"\w+", section["content"]))

        return [section for section in section_nodes if section["heading_level"] == 1]

    @staticmethod
    def extract_back_matter(pages):
        references_content = []
        references_start = None
        references_end = None
        for page in pages:
            page_num = page.get("page_number", page.get("page_num", 1))
            for line in page.get("lines", []):
                text = normalize_line(line.get("text", ""))
                if text.lower() == "references":
                    references_start = page_num
                    references_end = page_num
                    references_content.append(text)
                    continue
                if references_start is not None:
                    references_content.append(text)
                    references_end = page_num
        return {
            "references": {
                "page_start": references_start,
                "page_end": references_end,
                "content": "\n".join(references_content).strip(),
            },
            "appendices": [],
        }

    def run(self, job: IngestionJob, context: dict) -> dict:
        start_time = context.get("start_time", time.perf_counter())
        pages = context.get("classified_pages", [])
        sections = self.extract_project_sections(pages)
        back_matter = self.extract_back_matter(pages)

        draft = context.get("draft_metadata", {})
        draft["project_sections"] = sections
        draft["back_matter"] = back_matter
        references = back_matter["references"]
        draft["references"] = (
            [{"title": "References", "citation": references["content"]}]
            if references["content"]
            else []
        )
        draft["appendices"] = back_matter["appendices"]

        processing_time_ms = int(round((time.perf_counter() - start_time) * 1000))
        draft["document_metadata"] = {
            "processing_time_ms": processing_time_ms,
            "structural_confidence_score": 0.98,
            "sha256_hash": context.get("file_hash", getattr(job, "file_hash", "")),
        }

        context["draft_metadata"] = draft
        self.log(job, f"Extracted {len(sections)} section node(s) and back matter in {processing_time_ms}ms.")
        return context
