"""Synthetic manual grants for legacy regressions; production validation stays real."""
import json
import secrets
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import ai_policy


@dataclass(frozen=True)
class ManualRun:
    intent: str
    task_id: str

    @property
    def stage_kwargs(self):
        return {"manual_intent": self.intent, "manual_task_id": self.task_id}

    def run_task(self, task, *args, **kwargs):
        task.push_request(id=self.task_id)
        try:
            return task.run(*args, **kwargs, manual_intent=self.intent)
        finally:
            task.pop_request()


class ManualStore:
    def __init__(self):
        self.values = {}
        self.expirations = {}

    def set(self, key, value, ex=None):
        self.values[key] = value
        self.expirations[key] = time.time() + ex if ex else None
        return True

    def get(self, key):
        expires_at = self.expirations.get(key)
        if expires_at is not None and expires_at <= time.time():
            self.delete(key)
        return self.values.get(key)

    def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)
            self.expirations.pop(key, None)

    def issue(self, workflow, target):
        run = ManualRun(secrets.token_urlsafe(32), str(uuid.uuid4()))
        grant = {"workflow": workflow, "target": target, "task_id": run.task_id,
                 "expires_at": time.time() + ai_policy.GRANT_TTL_SECONDS}
        self.set(f"manual-ai:grant:{run.intent}", json.dumps(grant), ex=ai_policy.GRANT_TTL_SECONDS)
        assert ai_policy.manual_allowed(run.intent, (workflow,), target, run.task_id)
        assert not ai_policy.manual_allowed(run.intent, (workflow,), target, "unrelated-task")
        assert not ai_policy.manual_allowed(run.intent, (workflow,), "unrelated-target", run.task_id)
        assert not ai_policy.manual_allowed(run.intent, ("unrelated-workflow",), target, run.task_id)
        return run


@pytest.fixture
def manual_store(monkeypatch):
    """Replace only Redis storage, never the policy predicate or HTTP owner guard."""
    store = ManualStore()
    monkeypatch.setattr(ai_policy, "_store", lambda: store)
    return store


def assert_queued_grant(mock_send, response, workflow, target):
    mock_send.assert_called_once()
    call = mock_send.call_args.kwargs
    assert response["task_id"] == call["task_id"]
    assert ai_policy.manual_allowed(call["kwargs"]["manual_intent"], (workflow,), target, call["task_id"])
    return call


@contextmanager
def local_task_delivery(task):
    """Deliver this exact API-issued task locally; never construct a broker client."""
    def execute(*, kwargs, task_id):
        task.push_request(id=task_id)
        try:
            result = task.run(**kwargs)
            return SimpleNamespace(id=task_id, result=result)
        finally:
            task.pop_request()

    from unittest.mock import patch
    with patch.object(task, "apply_async", side_effect=execute) as send:
        yield send


def queued_task_result(*, task_id, **_kwargs):
    return SimpleNamespace(id=task_id)
