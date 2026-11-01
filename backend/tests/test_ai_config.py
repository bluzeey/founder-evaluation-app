"""Readiness uses the actual authenticated app and never probes providers."""


def test_readiness_remains_protected_and_uncached_without_a_key(client, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-old-key")
    monkeypatch.setenv("UMANS_API_KEY", "synthetic-old-key")
    response = client.get("/v1/ai/config")
    assert response.status_code == 200
    assert response.json() == {
        "enabled": False, "mode": "manual", "provider": "openrouter",
        "reason": "setup_pending", "message": "AI setup pending",
    }
    assert "no-store" in response.headers["cache-control"]
    client.cookies.clear()
    assert client.get("/v1/ai/config").status_code == 401
