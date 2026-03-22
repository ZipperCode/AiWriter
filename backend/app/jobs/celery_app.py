"""Celery application configuration with 3 queues."""

from celery import Celery
from kombu import Queue

from app.config import settings

celery_app = Celery(
    "aiwriter",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_queues=(
        Queue("default"),
        Queue("writing"),
        Queue("audit"),
    ),
    task_default_queue="default",
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_soft_time_limit=300,
    task_time_limit=600,
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    task_track_started=True,
    task_acks_late=True,
    timezone="UTC",
)

celery_app.autodiscover_tasks(["app.jobs"])
