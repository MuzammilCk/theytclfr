from typing import Any

from celery import Task

from ytclfr.core.logging import get_logger

logger = get_logger(__name__)


class BaseExtractorTask(Task):  # type: ignore[misc]
    """Base class for all ytclfr extractor Celery tasks.

    Provides:
    - Standard max_retries=3, retry_backoff=True
    - on_failure() hook that logs structured error data
    - on_retry() hook that logs retry count and reason
    - Abstract run_extraction() that subclasses implement

    Subclasses set:
      name: str  (Celery task name)
      extractor_type: str  ("asr", "ocr", "audio")
    """

    abstract = True
    max_retries = 3
    default_retry_delay = 30

    def on_failure(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        job_id = args[0] if args else "unknown"
        logger.error(
            "Extractor task failed permanently.",
            extra={
                "task_name": self.name,
                "task_id": task_id,
                "job_id": job_id,
                "error": str(exc),
                "retries_exhausted": True,
            },
        )

    def on_retry(
        self,
        exc: Exception,
        task_id: str,
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        einfo: Any,
    ) -> None:
        job_id = args[0] if args else "unknown"
        logger.warning(
            "Extractor task retrying.",
            extra={
                "task_name": self.name,
                "task_id": task_id,
                "job_id": job_id,
                "retry_number": self.request.retries,
                "error": str(exc),
            },
        )
