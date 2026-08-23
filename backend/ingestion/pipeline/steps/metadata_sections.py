import re
import time
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep
from ingestion.pipeline.utils.section_tree import (
    FOOTER_PAGE_NUMBER,
    back_matter_kind,
    build_section_tree,
    content_body_font_size,
    content_pages_with_toc_guard,
    detect_running_lines,
    first_nonempty_line_index,
    last_nonempty_line_index,
)
from ingestion.pipeline.utils.text_cleaners import normalize_line


class MetadataSectionsStep(BasePipelineStep):
    step_name = "Sections & Back Matter Extraction"

    @classmethod
    def extract_project_sections(cls, pages, warnings=None):
        """Builds the nested document tree for the report body. See
        section_tree.build_section_tree for the heading-acceptance and
        nesting rules -- this no longer requires numbering or an alias-table
        hit to recognize a heading; both are supporting evidence in a
        confidence score, not hard gates, so a differently-worded or
        unnumbered report still produces real sections instead of zero."""
        return build_section_tree(pages, warnings=warnings)

    @classmethod
    def extract_back_matter(cls, pages):
        references_content = []
        references_start = None
        references_end = None
        appendices = []
        seen_appendix_titles = set()
        current_appendix = None
        in_references = False

        total_pages = max(
            (page.get("page_number", page.get("page_num", 1)) for page in pages),
            default=1,
        )
        back_matter_min_page = total_pages / 2
        running_lines = detect_running_lines(pages)

        for page in content_pages_with_toc_guard(pages):
            page_num = page.get("page_number", page.get("page_num", 1))
            page_lines = page.get("lines", [])
            first_content_idx = first_nonempty_line_index(page_lines)
            last_content_idx = last_nonempty_line_index(page_lines)
            for idx, line in enumerate(page_lines):
                text = normalize_line(line.get("text", ""))
                if idx == last_content_idx and FOOTER_PAGE_NUMBER.match(text):
                    continue
                if idx in (first_content_idx, last_content_idx) and text in running_lines:
                    continue
                kind = back_matter_kind(text)
                if kind == "references":
                    if page_num < back_matter_min_page:
                        # too early — false hit, not real References section
                        in_references = False
                        current_appendix = None
                        continue
                    if not in_references:
                        references_start = page_num
                        in_references = True
                    references_end = page_num
                    references_content.append(text)
                    current_appendix = None
                    continue
                if kind == "appendices":
                    if page_num < back_matter_min_page:
                        current_appendix = None
                        continue
                    title_key = text.strip().lower()
                    if title_key in seen_appendix_titles:
                        for appx in appendices:
                            if appx["title"].strip().lower() == title_key:
                                current_appendix = appx
                                break
                        continue
                    seen_appendix_titles.add(title_key)
                    current_appendix = {
                        "title": text,
                        "page_start": page_num,
                        "page_end": page_num,
                        "content": text,
                    }
                    appendices.append(current_appendix)
                    continue
                if current_appendix is not None:
                    if text:
                        current_appendix["content"] += f"\n{text}"
                    current_appendix["page_end"] = page_num
                elif in_references:
                    references_content.append(text)
                    references_end = page_num

        return {
            "references": {
                "page_start": references_start,
                "page_end": references_end,
                "content": "\n".join(references_content).strip(),
            },
            "appendices": appendices,
        }

    def run(self, job: IngestionJob, context: dict) -> dict:
        start_time = context.get("start_time", time.perf_counter())
        pages = context.get("classified_pages", [])
        warnings = []
        sections = self.extract_project_sections(pages, warnings=warnings)
        back_matter = self.extract_back_matter(pages)

        draft = context.get("draft_metadata", {})
        draft["project_sections"] = sections
        references = back_matter["references"]
        draft["references"] = (
            [{
                "title": "References",
                "citation": references["content"],
                "page_start": references["page_start"],
                "page_end": references["page_end"],
            }]
            if references["content"]
            else []
        )
        draft["appendices"] = back_matter["appendices"]
        draft["processing_warnings"] = draft.get("processing_warnings", []) + warnings

        processing_time_ms = int(round((time.perf_counter() - start_time) * 1000))
        draft["document_metadata"] = {
            "processing_time_ms": processing_time_ms,
            "structural_confidence_score": 0.98,
            "sha256_hash": context.get("file_hash", getattr(job, "file_hash", "")),
        }

        def _count_nodes(nodes):
            total = 0
            for node in nodes:
                total += 1
                total += _count_nodes(node["children"])
            return total

        context["draft_metadata"] = draft
        self.log(
            job,
            f"Extracted {_count_nodes(sections)} section node(s) "
            f"({len(sections)} top-level) and back matter in {processing_time_ms}ms."
            + (f" {len(warnings)} hierarchy warning(s)." if warnings else ""),
        )
        return context
