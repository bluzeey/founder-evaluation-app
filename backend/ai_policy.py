"""Manual-only AI policy. No environment switch can re-enable automatic work.

Only protected HTTP handlers issue grants. Each opaque, short-lived grant names
one task id, workflow and target; it is not a blanket Celery context flag.
Legacy messages have no grant and return before Redis, DB or provider access.
"""
import json
import os
import secrets
import time
import uuid
from typing import Optional

import redis
from fastapi import HTTPException, Request
from research.openrouter_config import SETUP_PENDING, readiness

GRANT_TTL_SECONDS = 1800
STATUS_TTL_SECONDS = 86400


async def require_manual_ai(request: Request):
    """The session middleware sets this only after Google session validation."""
    if not getattr(request.state, "owner_email", None):
        raise HTTPException(401, "Sign in with Google before running AI")
    # Status/config reads remain available when setup is pending.
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        require_ai_ready()


def require_ai_ready():
    if not readiness()["enabled"]:
        raise HTTPException(503, SETUP_PENDING)


def _store():
    return redis.from_url(
        os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/0"),
        decode_responses=True, socket_connect_timeout=2, socket_timeout=2,
    )


def skipped_manual_required(**details):
    return {"status": "skipped_manual_required", "reason": "manual_required", **details}


def manual_allowed(intent: Optional[str], workflows, target: str, task_id: Optional[str]) -> bool:
    # Recheck in workers too: a previously issued grant cannot bypass setup.
    if not readiness()["enabled"]:
        return False
    if not isinstance(intent, str) or not intent or not task_id:
        return False
    try:
        raw = _store().get(f"manual-ai:grant:{intent}")
        grant = json.loads(raw) if raw else {}
        return (grant.get("workflow") in workflows and grant.get("target") == target
                and grant.get("task_id") == task_id and grant.get("expires_at", 0) > time.time())
    except Exception:
        # Missing/expired grants and unavailable Redis fail closed; never log secrets.
        return False


def queue_manual_task(task, workflow: str, target: str, **kwargs):
    """Called only by protected manual HTTP handlers, never by task dispatchers."""
    require_ai_ready()
    intent = secrets.token_urlsafe(32)
    task_id = str(uuid.uuid4())
    grant = {"workflow": workflow, "target": target, "task_id": task_id,
             "expires_at": time.time() + GRANT_TTL_SECONDS}
    grant_key = f"manual-ai:grant:{intent}"
    status_key = f"manual-ai:task:{task_id}"
    store = None
    try:
        store = _store()
        store.set(grant_key, json.dumps(grant), ex=GRANT_TTL_SECONDS)
        store.set(status_key, json.dumps(grant), ex=STATUS_TTL_SECONDS)
        return task.apply_async(kwargs={**kwargs, "manual_intent": intent}, task_id=task_id)
    except Exception:
        if store is not None:
            try:
                store.delete(grant_key, status_key)
            except Exception:
                pass
        raise HTTPException(503, "Could not queue AI. Please try the manual button again.") from None


def task_status(task_id: str):
    from celery_app import app
    try:
        raw = _store().get(f"manual-ai:task:{task_id}")
        grant = json.loads(raw) if raw else None
        if not grant:
            raise HTTPException(404, "Manual AI task not found")
        job = app.AsyncResult(task_id)
        state = job.state
        result = job.result if state == "SUCCESS" and isinstance(job.result, dict) else {}
        if state == "FAILURE":
            return {"task_id": task_id, "status": "failed", "error": "AI task failed. You can retry manually."}
        if state == "SUCCESS":
            status = result.get("status", "completed")
            error = None
            if status == "failed":
                error = "AI workflow failed in one or more stages. You can retry manually."
            elif status == "skipped_manual_required":
                error = "Manual request expired. Run the button again."
            return {"task_id": task_id, "status": status, "error": error}
        if state == "PENDING" and grant.get("expires_at", 0) <= time.time():
            return {"task_id": task_id, "status": "skipped_manual_required",
                    "error": "Manual request expired before a worker started it. Run the button again."}
        # Polling never queues or retries AI.
        return {"task_id": task_id, "status": "running" if state == "STARTED" else "queued"}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Could not read AI task status") from None
