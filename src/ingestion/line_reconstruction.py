"""
Line Reconstruction Engine.

Repairs broken sentences / line wraps produced by raw layout extraction --
most importantly, merging a heading number that landed on its own line
(e.g. "1.") back together with its title on the following line
("Introduction" -> "1 Introduction").
"""

import re


class LineReconstructor:

    # Matches: 1 / 1. / 1.1 / 1.1. / 2.3.4 / 10.2
    HEADING_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)*\.?$")

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

                new_lines.append(current)
                i += 1

            reconstructed_pages.append({
                "page_number": page["page_number"],
                "lines": new_lines,
            })

        return reconstructed_pages
