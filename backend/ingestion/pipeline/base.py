from abc import ABC, abstractmethod
from ingestion.models import IngestionJobLog


class BasePipelineStep(ABC):
    step_name: str = "Base Step"

    def log(self, job, message: str, level: str = "INFO"):
        IngestionJobLog.objects.create(
            job=job,
            level=level,
            message=f"[{self.step_name}] {message}"
        )

    @abstractmethod
    def run(self, job, context: dict) -> dict:
        """
        Executes the step.
        Parameters:
            job: IngestionJob instance
            context: mutable dictionary passed between steps
        Returns:
            updated context dictionary
        """
        pass
