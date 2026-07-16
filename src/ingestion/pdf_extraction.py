"""
Layout-Preserving PDF Extraction Service.

Extracts raw structural text layout elements (bounding boxes, font info,
block/line numbers) from each page of a PDF using PyMuPDF, instead of
reading the file as plain text.
"""

import fitz


class PDFLayoutExtractor:

    @staticmethod
    def extract_pages(file_path):
        pdf = fitz.open(file_path)
        pages = []

        for page_index, page in enumerate(pdf):
            page_dict = page.get_text("dict")
            extracted_lines = []
            block_number = 0

            for block in page_dict["blocks"]:
                if "lines" not in block:
                    continue

                line_number = 0
                for line in block["lines"]:
                    spans = line.get("spans", [])
                    if not spans:
                        continue

                    text = "".join(span["text"] for span in spans).strip()
                    if not text:
                        continue

                    font_size = max(span["size"] for span in spans)
                    font_name = spans[0]["font"]
                    is_bold = any("bold" in span["font"].lower() for span in spans)

                    extracted_lines.append({
                        "text": text,
                        "font_size": round(font_size, 2),
                        "font_name": font_name,
                        "is_bold": is_bold,
                        "bbox": line["bbox"],
                        "block_number": block_number,
                        "line_number": line_number,
                    })

                    line_number += 1
                block_number += 1

            pages.append({
                "page_number": page_index + 1,
                "lines": extracted_lines,
            })

        pdf.close()
        return pages
