import hashlib
from ingestion.models import IngestionJob
from ingestion.pipeline.base import BasePipelineStep


class HashDedupStep(BasePipelineStep):
    step_name = "SHA-256 Hashing & Deduplication"

    def run(self, job: IngestionJob, context: dict) -> dict:
        sha256 = hashlib.sha256()
        with open(job.file.path, "rb") as f:
            for block in iter(lambda: f.read(65536), b""):
                sha256.update(block)
        file_hash = sha256.hexdigest()

        job.file_hash = file_hash
        context["file_hash"] = file_hash

        # Check for existing job with same hash that completed or verified
        duplicate_exists = IngestionJob.objects.filter(
            file_hash=file_hash,
            status__in=[IngestionJob.Status.EXTRACTED, IngestionJob.Status.VERIFIED]
        ).exclude(id=job.id).exists()

        if duplicate_exists:
            job.status = IngestionJob.Status.DUPLICATE
            job.save(update_fields=["file_hash", "status", "updated_at"])
            context["stop_pipeline"] = True
            self.log(job, f"Duplicate file signature detected ({file_hash[:12]}). Pipeline stopped.", level="WARNING")
        else:
            job.save(update_fields=["file_hash", "updated_at"])
            self.log(job, f"SHA-256 fingerprint generated: {file_hash[:12]}")

        return context
