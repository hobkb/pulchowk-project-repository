from celery import shared_task
from ingestion.models import IngestionJob
from ingestion.pipeline.runner import PipelineRunner


@shared_task(bind=True)
def run_ingestion_pipeline(self, job_id: str):
    job = IngestionJob.objects.get(id=job_id)
    runner = PipelineRunner()
    runner.execute(job)
