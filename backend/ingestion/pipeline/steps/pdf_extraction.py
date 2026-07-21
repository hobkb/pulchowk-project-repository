import fitz
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep


class PDFExtractionStep(BasePipelineStep):
    step_name = "PDF Layout Extraction"

    def run(self, job: IngestionJob, context: dict) -> dict:
        file_path = job.file.path
        pdf = fitz.open(file_path)
        pages = []

        for page_index, page in enumerate(pdf):
            page_dict = page.get_text("dict")
            extracted_lines = []
            block_number = 0
            blocks = page_dict.get("blocks", [])

            # preserve visual reading order
            blocks = sorted(
                blocks,
                key=lambda block: (
                    block.get("bbox", [0, 0, 0, 0])[1],
                    block.get("bbox", [0, 0, 0, 0])[0]
                )
            )

            for block in blocks:
                if "lines" not in block:
                    continue

                line_number = 0
                lines = sorted(
                    block["lines"],
                    key=lambda line: (line["bbox"][1], line["bbox"][0])
                )

                for line in lines:
                    spans = line.get("spans", [])
                    if not spans:
                        continue

                    text_parts = [span.get("text", "") for span in spans if span.get("text", "")]
                    text = " ".join(text_parts).strip()
                    if not text:
                        continue

                    font_size = max(span.get("size", 0) for span in spans)
                    font_name = spans[0].get("font", "")
                    is_bold = any("bold" in span.get("font", "").lower() for span in spans)

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
                "width": page.rect.width,
                "height": page.rect.height,
                "lines": extracted_lines
            })

        pdf.close()
        context["raw_pages"] = pages
        self.log(job, f"Extracted layout structure from {len(pages)} pages.")
        return context
