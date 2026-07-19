import logging
import os

from celery import Celery

from logger_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)

REDIS_BROKER = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/0")
REDIS_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

POOL_REFRESH_INTERVAL_SECONDS = float(
    os.environ.get("POOL_REFRESH_INTERVAL_SECONDS", "3600")
)

app = Celery("founderos", broker=REDIS_BROKER, backend=REDIS_BACKEND)

app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_always_eager=os.environ.get("CELERY_ALWAYS_EAGER", "false").lower() == "true",
    beat_schedule={
        "refresh-founder-pool": {
            "task": "tasks.founder_pool.refresh_pool_task",
            "schedule": POOL_REFRESH_INTERVAL_SECONDS,
            "args": (),
        },
    },
)

app.conf.imports = ("tasks.social_research", "tasks.founder_pool")

logger.info(
    "celery_app.configured broker=%s backend=%s pool_refresh_interval_seconds=%s always_eager=%s",
    REDIS_BROKER,
    REDIS_BACKEND,
    POOL_REFRESH_INTERVAL_SECONDS,
    app.conf.task_always_eager,
)
