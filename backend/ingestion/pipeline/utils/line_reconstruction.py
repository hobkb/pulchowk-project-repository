"""
Line Reconstruction Engine.
Repairs broken sentences / line wraps produced by raw layout extraction.
"""

import re

from ingestion.pipeline.utils.heading_utils import looks_like_heading


class LineReconstructor:

    # Matches: 1 / 1. / 1.1 / 1.1. / 2.3.4 / 10.2
    HEADING_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)*\.?$")

    # A standalone "Chapter N" / "Chapter IV:" marker with no title on the
    # same rendered line -- common in report templates that put the chapter
    # label and its title on two separate lines ("CHAPTER I" / newline /
    # "INTRODUCTION"). Merged the same way HEADING_NUMBER_PATTERN merges
    # "1." + "Introduction", so heading detection downstream always sees one
    # combined line rather than a title-less marker plus an orphaned title.
    CHAPTER_MARKER_PATTERN = re.compile(r"^chapter\s+(?:[ivxlcdm]+|\d+)\s*[.:]?$", re.IGNORECASE)

    # A word-wrap hyphen at the end of a rendered PDF line, e.g. "imple-"
    # continuing as "mentation" on the next line. Excludes dashes used as
    # punctuation (preceded by a space) so "state-of-the-art -" style lines
    # are left untouched.
    WORD_WRAP_HYPHEN = re.compile(r"[A-Za-z]-$")

    @staticmethod
    def _is_hyphenated_wrap(current, nxt):
        # Only merge lines PyMuPDF placed in the same layout block/column --
        # this prevents stitching the end of one column/paragraph onto the
        # start of an unrelated one that merely follows it in reading order.
        if current.get("block_number") != nxt.get("block_number"):
            return False
        current_text = current["text"].strip()
        next_text = nxt["text"].strip()
        if not next_text or not LineReconstructor.WORD_WRAP_HYPHEN.search(current_text):
            return False
        return next_text[0].islower()

    @staticmethod
    def reconstruct(pages):
        reconstructed_pages = []

        for page in pages:
            lines = page["lines"]
            new_lines = []
            i = 0

            while i < len(lines):
                current = lines[i]
                current_text = current["text"].strip()

                # Merge heading number + heading title, e.g. "1." + "Introduction" -> "1 Introduction"
                if (
                    LineReconstructor.HEADING_NUMBER_PATTERN.match(current_text)
                    and i + 1 < len(lines)
                ):
                    nxt = lines[i + 1]
                    next_text = nxt["text"].strip()

                    if re.match(r"^[A-Za-z]", next_text):
                        merged = current.copy()
                        merged["text"] = current_text.rstrip(".") + " " + next_text
                        merged["font_size"] = max(current["font_size"], nxt["font_size"])
                        merged["is_bold"] = current["is_bold"] or nxt["is_bold"]

                        new_lines.append(merged)
                        i += 2
                        continue

                # Merge a standalone "Chapter N" marker with its title on
                # the next line, e.g. "CHAPTER I" + "INTRODUCTION" ->
                # "CHAPTER I INTRODUCTION" -- only when the following line
                # actually looks heading-shaped, so a "Chapter 3" marker
                # immediately followed by ordinary body prose is left alone.
                if (
                    LineReconstructor.CHAPTER_MARKER_PATTERN.match(current_text)
                    and i + 1 < len(lines)
                ):
                    nxt = lines[i + 1]
                    next_text = nxt["text"].strip()
                    if next_text and looks_like_heading(next_text):
                        merged = current.copy()
                        merged["text"] = current_text + " " + next_text
                        merged["font_size"] = max(current["font_size"], nxt["font_size"])
                        merged["is_bold"] = current["is_bold"] or nxt["is_bold"]

                        new_lines.append(merged)
                        i += 2
                        continue

                # Rejoin a word split across a line wrap, e.g. "imple-" + "mentation" -> "implementation".
                # Chains across more than one wrap in the same block, e.g. a word
                # broken twice in a row in a narrow column.
                if i + 1 < len(lines) and LineReconstructor._is_hyphenated_wrap(current, lines[i + 1]):
                    merged = current.copy()
                    merged_text = current_text
                    j = i
                    while j + 1 < len(lines) and LineReconstructor._is_hyphenated_wrap(lines[j], lines[j + 1]):
                        nxt = lines[j + 1]
                        merged_text = merged_text[:-1] + nxt["text"].strip()
                        merged["font_size"] = max(merged["font_size"], nxt["font_size"])
                        merged["is_bold"] = merged["is_bold"] or nxt["is_bold"]
                        j += 1
                    merged["text"] = merged_text

                    new_lines.append(merged)
                    i = j + 1
                    continue

                new_lines.append(current)
                i += 1

            reconstructed_pages.append({
                "page_number": page["page_number"],
                "lines": new_lines,
            })

        return reconstructed_pages
