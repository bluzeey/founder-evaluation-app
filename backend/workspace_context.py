"""Verified request/worker identity, never an email or client-supplied tenant."""
from contextlib import contextmanager
from contextvars import ContextVar

_user_id = ContextVar("founderos_workspace_user", default=None)


def validate_user_id(value):
    if type(value) is not int or not 0 < value <= 2_147_483_647:
        raise RuntimeError("A verified workspace identity is required")
    return value


def current_user_id():
    return validate_user_id(_user_id.get())


@contextmanager
def user_scope(user_id):
    token = _user_id.set(validate_user_id(user_id))
    try:
        yield
    finally:
        _user_id.reset(token)
