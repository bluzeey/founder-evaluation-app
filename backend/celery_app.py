import os

from celery import Celery

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
    beat_schedule={
        "refresh-founder-pool": {
            "task": "tasks.founder_pool.refresh_pool_task",
            "schedule": 3600.0,
            "args": (),
        },
    },
)

app.conf.imports = ("tasks.social_research", "tasks.founder_pool")
