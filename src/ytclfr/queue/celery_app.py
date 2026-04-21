from celery import Celery
from kombu import Queue

from ytclfr.core.config import Settings, get_settings


def build_celery_app(settings: Settings) -> Celery:
    app = Celery("ytclfr")
    app.conf.update(
        broker_url=settings.redis_url,
        result_backend=settings.redis_url,
        task_queues=[
            Queue("fast"),
            Queue("heavy"),
        ],
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        task_time_limit=settings.celery_task_time_limit,
        task_soft_time_limit=settings.celery_task_time_limit - 60,
        worker_prefetch_multiplier=1,
        broker_connection_retry_on_startup=True,
    )
    return app


celery_app = build_celery_app(get_settings())
import ytclfr.tasks.align  # noqa: F401, E402
import ytclfr.tasks.extract  # noqa: F401, E402
import ytclfr.tasks.ingest  # noqa: F401, E402
import ytclfr.tasks.route  # noqa: F401, E402
