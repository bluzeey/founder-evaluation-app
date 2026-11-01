"""Manual-only AI policy. No environment switch can re-enable automatic work.

Only protected HTTP handlers issue grants. Each opaque, short-lived grant names
one actor, task id, workflow and target; it is not a blanket Celery context flag.
Legacy messages have no grant and return before Redis, DB or provider access.
"""
import json
import math
import os
import secrets
import time
import uuid
from typing import Optional

import redis
from fastapi import HTTPException, Request
from research.openrouter_config import SETUP_PENDING, readiness
from workspace_context import current_user_id, validate_user_id

GRANT_TTL_SECONDS = 1800
STATUS_TTL_SECONDS = 86400


async def require_manual_ai(request: Request):
    """The session middleware sets this only after Google session validation."""
    actor = getattr(request.state, "user_id", None)
    if not _valid_actor(actor):
        raise HTTPException(401, "Sign in with Google before running AI")
    if _request_actor() != actor:
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


def _valid_actor(actor) -> bool:
    # bool, numeric strings and floats must never alias another user's id.
    try:
        validate_user_id(actor)
        return True
    except RuntimeError:
        return False


def _request_actor() -> int:
    try:
        actor = current_user_id()
    except RuntimeError:
        raise HTTPException(401, "Sign in with Google before running AI") from None
    if not _valid_actor(actor):
        raise HTTPException(401, "Sign in with Google before running AI")
    return actor


def manual_allowed(intent: Optional[str], workflows, target: str, task_id: Optional[str],
                   manual_actor_id: Optional[int] = None) -> Optional[int]:
    """Return the grant's validated actor, never an ambient worker identity.

    Callers must enter user_scope(actor) around the entire admitted workflow.
    Missing legacy credentials return before context, Redis or provider access.
    """
    if (not isinstance(intent, str) or not intent or not isinstance(task_id, str)
            or not task_id or not _valid_actor(manual_actor_id)):
        return None
    # Recheck in workers too: a previously issued grant cannot bypass setup.
    if not readiness()["enabled"]:
        return None
    try:
        raw = _store().get(f"manual-ai:grant:{intent}")
        grant = json.loads(raw) if raw else {}
        if not isinstance(grant, dict):
            return None
        expires_at = grant.get("expires_at")
        if (grant.get("workflow") in workflows and grant.get("target") == target
                and grant.get("intent") == intent and grant.get("task_id") == task_id
                and _valid_actor(grant.get("actor_id")) and grant["actor_id"] == manual_actor_id
                and type(expires_at) in (int, float) and math.isfinite(expires_at)
                and expires_at > time.time()):
            return grant["actor_id"]
        return None
    except Exception:
        # Missing/expired grants and unavailable Redis fail closed; never log secrets.
        return None


def queue_manual_task(task, workflow: str, target: str, **kwargs):
    """Called only by protected manual HTTP handlers, never by task dispatchers."""
    require_ai_ready()
    actor = _request_actor()
    intent = secrets.token_urlsafe(32)
    task_id = str(uuid.uuid4())
    grant = {"workflow": workflow, "target": target, "task_id": task_id,
             "actor_id": actor, "intent": intent,
             "expires_at": time.time() + GRANT_TTL_SECONDS}
    grant_key = f"manual-ai:grant:{intent}"
    status_key = f"manual-ai:task:{task_id}"
    store = None
    try:
        store = _store()
        store.set(grant_key, json.dumps(grant), ex=GRANT_TTL_SECONDS)
        store.set(status_key, json.dumps(grant), ex=STATUS_TTL_SECONDS)
        return task.apply_async(kwargs={**kwargs, "manual_intent": intent,
                                        "manual_actor_id": actor}, task_id=task_id)
    except Exception:
        if store is not None:
            try:
                store.delete(grant_key, status_key)
            except Exception:
                pass
        raise HTTPException(503, "Could not queue AI. Please try the manual button again.") from None


def task_status(task_id: str):
    actor = _request_actor()
    from celery_app import app
    try:
        raw = _store().get(f"manual-ai:task:{task_id}")
        grant = json.loads(raw) if raw else None
        if (not isinstance(grant, dict) or not _valid_actor(grant.get("actor_id"))
                or grant["actor_id"] != actor or grant.get("task_id") != task_id):
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
