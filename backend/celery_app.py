import logging
import os

from celery import Celery

from logger_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

REDIS_BROKER = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
REDIS_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

app = Celery("founderos", broker=REDIS_BROKER, backend=REDIS_BACKEND)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=os.environ.get("CELERY_ALWAYS_EAGER", "false").lower() == "true",
    beat_schedule={},
)

app.conf.imports = (
    "tasks.social_research",
    "tasks.founder_pool",
    "tasks.document_extraction",
    "tasks.estimation_task",
    "tasks.enrichment_task",
)

logger.info(
    "celery_app.configured broker_configured=%s backend_configured=%s ai_mode=manual beat_enabled=false always_eager=%s",
    bool(REDIS_BROKER),
    bool(REDIS_BACKEND),
    app.conf.task_always_eager,
)
