import time
import traceback
from ingestion.models import IngestionJob, IngestionJobLog
from notifications.services import NotificationService
from ingestion.pipeline.steps.hash_dedup import HashDedupStep
from ingestion.pipeline.steps.pdf_extraction import PDFExtractionStep
from ingestion.pipeline.steps.line_reconstruction import LineReconstructionStep
from ingestion.pipeline.steps.page_classification import PageClassificationStep
from ingestion.pipeline.steps.metadata_front_matter import MetadataFrontMatterStep
from ingestion.pipeline.steps.metadata_people import MetadataPeopleStep
from ingestion.pipeline.steps.metadata_sections import MetadataSectionsStep


class PipelineRunner:
    STEPS = [
        HashDedupStep(),
        PDFExtractionStep(),
        LineReconstructionStep(),
        PageClassificationStep(),
        MetadataFrontMatterStep(),
        MetadataPeopleStep(),
        MetadataSectionsStep(),
    ]

    def execute(self, job: IngestionJob) -> dict:
        job.status = IngestionJob.Status.PROCESSING
        job.error_message = None
        job.save(update_fields=["status", "error_message", "updated_at"])

        IngestionJobLog.objects.create(
            job=job,
            level="INFO",
            message="Ingestion pipeline started."
        )

        context = {
            "start_time": time.perf_counter(),
            "stop_pipeline": False,
        }

        try:
            for step in self.STEPS:
                context = step.run(job, context)
                if context.get("stop_pipeline"):
                    break

            if not context.get("stop_pipeline"):
                draft_metadata = context.get("draft_metadata", {})
                job.extracted_payload = draft_metadata
                job.status = IngestionJob.Status.EXTRACTED
                job.save(update_fields=["extracted_payload", "status", "updated_at"])

                IngestionJobLog.objects.create(
                    job=job,
                    level="INFO",
                    message="Ingestion pipeline completed successfully. Status set to EXTRACTED."
                )

                NotificationService.notify_job_ready_for_review(job)
                NotificationService.notify_job_awaiting_admin(job)

            return context

        except Exception as exc:
            error_text = str(exc) or exc.__class__.__name__
            job.status = IngestionJob.Status.FAILED
            job.error_message = f"{error_text}\n{traceback.format_exc()}"
            job.save(update_fields=["status", "error_message", "updated_at"])

            IngestionJobLog.objects.create(
                job=job,
                level="ERROR",
                message=f"Pipeline execution failed: {error_text}"
            )

            NotificationService.notify_job_failed(job)

            raise exc
