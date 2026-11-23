from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep
from ingestion.pipeline.utils.line_reconstruction import LineReconstructor


class LineReconstructionStep(BasePipelineStep):
    step_name = "Line Reconstruction"

    def run(self, job: IngestionJob, context: dict) -> dict:
        raw_pages = context.get("raw_pages", [])
        reconstructed = LineReconstructor.reconstruct(raw_pages)
        context["reconstructed_pages"] = reconstructed
        self.log(job, f"Line reconstruction completed for {len(reconstructed)} pages.")
        return context
