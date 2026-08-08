import re
import time
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep
from ingestion.pipeline.utils.heading_utils import looks_like_heading
from ingestion.pipeline.utils.text_cleaners import (
    normalize_line,
    TOC_ENTRY,
    canonicalize_heading,
)


class MetadataSectionsStep(BasePipelineStep):
    step_name = "Sections & Back Matter Extraction"

    MAJOR_SECTION_ALIASES = {
        # Introduction and context
      
        'background': 'Background',
        'context': 'Background',
        'introduction': 'Introduction',
        'introduction and background': 'Introduction',
        'problem background': 'Background',
        'problem context': 'Background',
        'problem statement': 'Problem Statement',
        'research background': 'Background',

        # Problem, objectives, and scope
       
        'objectives': 'Objectives',
        'project objectives': 'Objectives',
        'research objectives': 'Objectives',
        'project scope': 'Scope',
        'scope and limitations': 'Scope',
        'scope of the study': 'Scope',
        'significance of the study': 'Significance',
        'statement of the problem': 'Problem Statement',

        # Literature and related work
        'literature review': 'Literature Review',
        'literature survey': 'Literature Review',
        'related literature': 'Literature Review',
        'related studies': 'Related Work',
        'related work': 'Related Work',
        'review of literature': 'Literature Review',
        'state of the art': 'Related Work',

        # Analysis, requirements, and design
       
        'requirement analysis': 'Requirements Analysis',
        'requirements analysis': 'Requirements Analysis',
        'requirements specification': 'Requirements',
        'system analysis': 'System Analysis',
        'system architecture': 'System Design',
        'system design': 'System Design',
        'system overview': 'System Design',
        'system specification': 'System Design',

        # Methodology and approach
        'approach': 'Methodology',
        'methodology': 'Methodology',
        'method': 'Methodology',
        'methodology and design': 'Methodology',
        'proposed approach': 'Methodology',
        'proposed methodology': 'Methodology',
        'research methodology': 'Methodology',
        'research design': 'Methodology',
        'technical approach': 'Methodology',

        # Proposed system and implementation
        'implementation': 'Implementation',
        'implementation details': 'Implementation',
        'implementation methodology': 'Implementation',
        'proposed system': 'Proposed System',
        'system implementation': 'Implementation',
        'system development': 'Implementation',

        # Experimental setup and evaluation
        'experimental setup': 'Experiments',
        'experimental methodology': 'Experiments',
        'experimental results': 'Results',
        'experiments': 'Experiments',
        'experiments and results': 'Results',
        'experiments and evaluation': 'Evaluation',
        'performance analysis': 'Evaluation',
        'performance evaluation': 'Evaluation',
        'proposed experimental setup': 'Experiments',

        'test results': 'Results',
        'validation': 'Validation',
        
        
        # Data and dataset
        'data collection': 'Data Collection',
        'data acquisition': 'Data Collection',
        'data sources': 'Data Collection',

        'dataset': 'Dataset',
        'dataset description': 'Dataset',
        'dataset overview': 'Dataset',
        'data description': 'Dataset',

        # Data exploration
        'data exploration': 'Data Exploration',
        'exploratory data analysis': 'Data Exploration',
        'exploratory analysis': 'Data Exploration',
        'data analysis': 'Data Exploration',

        # Data preprocessing
        'data preprocessing': 'Data Preprocessing',
        'data pre-processing': 'Data Preprocessing',
        'data preparation': 'Data Preprocessing',
        'data cleaning': 'Data Preprocessing',

        # Results and discussion
        'analysis and discussion': 'Discussion',
        'discussion': 'Discussion',
        'discussion and analysis': 'Discussion',
        'results and findings': 'Results',
        'findings': 'Results',
        'results': 'Results',
        'results and analysis': 'Results',
        'results and discussion': 'Results',
        'result and discussion': 'Results',
        'results and discussions': 'Results',
        'results and findings': 'Results',
        'experimental results and findings': 'Results',
        'experimental results and discussion': 'Results',
        'experimental results and discussions': 'Results',
        'outcome': 'Results',
        'outcomes': 'Results',

        # Evaluation and comparison
        'comparison': 'Evaluation',
        'comparative analysis': 'Evaluation',
        'evaluation': 'Evaluation',
        'evaluation and analysis': 'Evaluation',
        'evaluation results': 'Evaluation',
        'performance comparison': 'Evaluation',
        'system evaluation': 'Evaluation',

        # Resources
        'resources': 'Resources',
        'resources used': 'Resources',
        'project resources': 'Resources',
        'project resource': 'Resources',
        'resource used': 'Resources',
        
        # Limitations and future work
        'future enhancement': 'Future Enhancement',
        'future enhancements': 'Future Enhancement',
        'future improvement': 'Future Enhancement',
        'future improvements': 'Future Enhancement',
        'future scope': 'Future Enhancement',
        'future work': 'Future Enhancement',
        'limitations': 'Limitations',
        'limitations and future enhancements': 'Future Enhancement',
        'limitations and future enhancement': 'Future Enhancement',
        'limitations and future work': 'Future Enhancement',

        "challenges faced":"Challenges",
        "challenges":"Challenges",
        
        # Conclusion and recommendations
        'conclusion': 'Conclusion',
        'conclusion and future work': 'Conclusion',
        'conclusions': 'Conclusion',
        'concluding remarks': 'Conclusion',
        'final remarks': 'Conclusion',
        'recommendation': 'Recommendations',
        'recommendations': 'Recommendations',
        'summary': 'Conclusion',
        'summary and conclusion': 'Conclusion',
        'summary and conclusions': 'Conclusion',
    }


    MIN_MAJOR_HEADING_FONT_SIZE = 14.0
    MIN_RECOVERY_HEADING_FONT_SIZE = 11.0
    TOC_DOT_LEADER = re.compile(r"\.{2,}\s*(?:[ivxlcdm]+|\d+|[a-z])?\s*$", re.IGNORECASE)
    SUBHEADING_PREFIX = re.compile(r"^\d+\.\d+(?:\.\d+)*[.) :\-]+")

    @staticmethod
    def _normalized_major_heading(text):
        text = normalize_line(text)
        text = re.sub(r"^chapter\s+(?:[ivxlcdm]+|\d+)\b[. :\-]*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"^\d+(?:\.\d+)*[.) :\-]+", "", text)
        return text.strip().rstrip(":")

    @staticmethod
    def _line_font_size(line):
        try:
            return float(line.get("font_size", 0))
        except (TypeError, ValueError):
            return 0.0

    @classmethod
    def _back_matter_heading(cls, text):
        """Return the back-matter kind for a heading, if this is one."""
        normalized = normalize_line(text).lower()
        normalized = re.sub(r"^chapter\s+(?:[ivxlcdm]+|\d+)\b[\s.:\-]*", "", normalized)
        normalized = re.sub(r"^\d+(?:\.\d+)*\.?\s+", "", normalized)
        if normalized in {"reference", "references", "bibliography"}:
            return "references"
        if re.match(
            r"^(?:appendices?|appendix\s*:\s*.*|appendix\s+(?:[a-z]|\d+|[ivxlcdm]+)(?:\s*:\s*.*)?)$",
            normalized,
        ):
            return "appendices"
        return None

    @classmethod
    def _content_body_font_size(cls, pages):
        sizes = sorted(
            cls._line_font_size(line)
            for page in pages
            if page.get("page_type") == "content"
            for line in page.get("lines", [])
            if normalize_line(line.get("text", ""))
            and not line.get("is_bold", False)
            and cls._line_font_size(line) > 0
        )
        return sizes[len(sizes) // 2] if sizes else 10.0

    @classmethod
    def _is_strict_major_heading(cls, line, candidate, body_font_size):
        return (
            bool(line.get("is_bold", False))
            and cls._line_font_size(line) >= cls.MIN_MAJOR_HEADING_FONT_SIZE
            and looks_like_heading(candidate)
        )

    @classmethod
    def _is_recovery_major_heading(cls, line, candidate, body_font_size):
        font_size = cls._line_font_size(line)
        return (
            looks_like_heading(candidate)
            and font_size >= cls.MIN_RECOVERY_HEADING_FONT_SIZE
            and (bool(line.get("is_bold", False)) or font_size >= body_font_size + 1.0)
        )

    @classmethod
    def _is_confirmed_back_matter_heading(cls, line, text, heading_rule, body_font_size):
        kind = cls._back_matter_heading(text)
        if not kind:
            return None
        candidate = cls._normalized_major_heading(text)
        return kind if heading_rule(line, candidate, body_font_size) else None

    @classmethod
    def _content_pages_with_toc_guard(cls, pages):
        in_toc_sequence = False
        for page in pages:
            if page.get("page_type") == "toc":
                in_toc_sequence = True
                continue
            dot_leader_count = sum(
                bool(cls.TOC_DOT_LEADER.search(normalize_line(line.get("text", ""))))
                for line in page.get("lines", [])
            )
            if in_toc_sequence and dot_leader_count:
                continue
            if page.get("page_type") == "content":
                in_toc_sequence = False
                yield page

    @classmethod
    def _extract_flat_sections(cls, pages, heading_rule, include_unsectioned_content=False):
        sections, current, in_back_matter = [], None, False
        body_font_size = cls._content_body_font_size(pages)
        for page in cls._content_pages_with_toc_guard(pages):
            page_num = page.get("page_number", page.get("page_num", 1))
            for line in page.get("lines", []):
                text = normalize_line(line.get("text", ""))
                if not text or TOC_ENTRY.search(text):
                    continue
                if cls._is_confirmed_back_matter_heading(line, text, heading_rule, body_font_size):
                    in_back_matter = True
                    current = None
                    continue
                if in_back_matter:
                    continue

                # Flat extraction deliberately keeps subheadings inside their
                # parent major section; aliases such as "Background" must not
                # promote a numbered 1.1 heading into its own section.
                if cls.SUBHEADING_PREFIX.match(text):
                    continue
                candidate = cls._normalized_major_heading(text)
                canonical = cls.MAJOR_SECTION_ALIASES.get(candidate.lower())
                if canonical and heading_rule(line, candidate, body_font_size):
                    current = {
                        "heading": canonical,
                        "canonical_section": canonicalize_heading(candidate),
                        "heading_level": 1,
                        "display_order": len(sections) + 1,
                        "page_start": page_num,
                        "page_end": page_num,
                        "content": "",
                    }
                    sections.append(current)
                    continue
                if current:
                    current["content"] += ("\n" if current["content"] else "") + text
                    current["page_end"] = page_num
                elif include_unsectioned_content and candidate:
                    current = {
                        "heading": "Unsectioned Content",
                        "canonical_section": "unsectioned_content",
                        "heading_level": 1,
                        "display_order": len(sections) + 1,
                        "page_start": page_num,
                        "page_end": page_num,
                        "content": text,
                    }
                    sections.append(current)

        for section in sections:
            section["word_count"] = len(re.findall(r"\w+", section["content"]))
        return sections

    @classmethod
    def extract_project_sections(cls, pages):
        sections = cls._extract_flat_sections(pages, cls._is_strict_major_heading)
        if len(sections) <= 2:
            sections = cls._extract_flat_sections(pages, cls._is_recovery_major_heading)
        if len(sections) <= 2:
            sections = cls._extract_flat_sections(
                pages,
                cls._is_recovery_major_heading,
                include_unsectioned_content=True,
            )
        return sections

    @classmethod
    def extract_back_matter(cls, pages):
        references_content = []
        references_start = None
        references_end = None
        appendices = []
        seen_appendix_titles = set()
        current_appendix = None
        in_references = False
        body_font_size = cls._content_body_font_size(pages)

        total_pages = max(
            (page.get("page_number", page.get("page_num", 1)) for page in pages),
            default=1,
        )
        back_matter_min_page = total_pages / 2

        for page in cls._content_pages_with_toc_guard(pages):
            page_num = page.get("page_number", page.get("page_num", 1))
            for line in page.get("lines", []):
                text = normalize_line(line.get("text", ""))
                back_matter_kind = cls._is_confirmed_back_matter_heading(
                    line, text, cls._is_recovery_major_heading, body_font_size
                )
                if back_matter_kind == "references":
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
                if back_matter_kind == "appendices":
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
        sections = self.extract_project_sections(pages)
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

        processing_time_ms = int(round((time.perf_counter() - start_time) * 1000))
        draft["document_metadata"] = {
            "processing_time_ms": processing_time_ms,
            "structural_confidence_score": 0.98,
            "sha256_hash": context.get("file_hash", getattr(job, "file_hash", "")),
        }

        context["draft_metadata"] = draft
        self.log(job, f"Extracted {len(sections)} section node(s) and back matter in {processing_time_ms}ms.")
        return context
