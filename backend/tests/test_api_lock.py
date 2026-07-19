import os
from unittest.mock import MagicMock, patch

import pytest
import redis

import research.api_lock as api_lock
from research.openai_client import OpenAIClient
from research.social_agent import SocialAgent
from research.sourcing_agent import SourcingAgent


def _mock_redis_client():
    """Return a mock Redis client with a working lock helper."""
    client = MagicMock()
    lock_instance = MagicMock()
    lock_instance.acquire.return_value = True
    client.lock.return_value = lock_instance
    client.exists.return_value = 0
    return client, lock_instance


def test_api_lock_acquires_and_releases():
    client, lock_instance = _mock_redis_client()
    with patch.object(api_lock, "_redis_client", return_value=client):
        with api_lock.api_lock():
            lock_instance.acquire.assert_called_once()
        lock_instance.release.assert_called_once()


def test_api_lock_releases_when_exception_raised():
    client, lock_instance = _mock_redis_client()
    with patch.object(api_lock, "_redis_client", return_value=client):
        with pytest.raises(RuntimeError):
            with api_lock.api_lock():
                raise RuntimeError("boom")
        lock_instance.release.assert_called_once()


def test_api_lock_raises_when_circuit_open():
    client, _ = _mock_redis_client()
    with patch.object(api_lock, "_redis_client", return_value=client):
        with patch.object(api_lock, "is_circuit_open", return_value=True):
            with pytest.raises(api_lock.LLMAPIOverload):
                with api_lock.api_lock():
                    pass  # pragma: no cover


def test_api_lock_degrades_when_redis_unavailable():
    with patch.object(
        api_lock, "_redis_client", side_effect=redis.RedisError("connection refused")
    ):
        with api_lock.api_lock():
            pass  # Should not raise


def test_circuit_breaker_opens_after_threshold_failures():
    client, _ = _mock_redis_client()
    # Simulate the failure counter crossing the threshold.
    client.incr.side_effect = [1, 2, 3]
    with patch.object(api_lock, "_redis_client", return_value=client):
        api_lock.record_api_failure()
        api_lock.record_api_failure()
        api_lock.record_api_failure()

    # After the third failure the circuit should be opened.
    client.set.assert_called_once()
    assert client.set.call_args[0][0] == api_lock.CIRCUIT_BREAKER_OPEN_KEY


def test_circuit_breaker_resets_on_success():
    client, _ = _mock_redis_client()
    with patch.object(api_lock, "_redis_client", return_value=client):
        api_lock.record_api_success()
    client.delete.assert_called_once_with(api_lock.CIRCUIT_BREAKER_FAILURES_KEY)


def test_sourcing_agent_web_search_defaults_true():
    agent = SourcingAgent(api_key="test-key")
    assert agent.enable_web_search is True


def test_social_agent_web_search_defaults_false():
    agent = SocialAgent(api_key="test-key")
    assert agent.enable_web_search is False


def test_openai_client_web_search_defaults_true():
    client = OpenAIClient(api_key="test-key")
    assert client.enable_web_search is True


def test_per_agent_web_search_overrides_legacy():
    # Legacy toggle is true but per-agent toggle is false.
    with patch.dict(
        os.environ,
        {"OPENAI_ENABLE_WEB_SEARCH": "true", "OPENAI_ENABLE_WEB_SEARCH_SOCIAL": "false"},
        clear=False,
    ):
        agent = SocialAgent(api_key="test-key")
        assert agent.enable_web_search is False

    # Legacy toggle is false but per-agent toggle is true.
    with patch.dict(
        os.environ,
        {"OPENAI_ENABLE_WEB_SEARCH": "false", "OPENAI_ENABLE_WEB_SEARCH_SOURCING": "true"},
        clear=False,
    ):
        agent = SourcingAgent(api_key="test-key")
        assert agent.enable_web_search is True
