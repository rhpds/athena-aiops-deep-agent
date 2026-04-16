"""End-to-end pipeline test with mocked LLM and external services.

Tests the full flow: webhook → ingestion → (mocked) agent → submission → Kira + Rocket.Chat.
This validates wiring without burning LLM tokens.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from athena.models import TicketPayload


@pytest.fixture
def mock_ticket_payload() -> TicketPayload:
    return TicketPayload(
        title="Deploy Web App failed: missing httpd package",
        description="The playbook task 'install httpd' failed because httpd is not in the repo.",
        area="application",
        confidence=85,
        risk="high",
        stage="production",
        recommended_action="Add httpd to the Satellite content view for the production repo.",
        affected_systems=["web-server-01"],
        skills=["linux", "ansible"],
        issues=[],
    )


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch):
    """Set all required env vars for Settings."""
    env = {
        "aap2_url": "https://aap2.test",
        "aap2_username": "admin",
        "aap2_password": "secret",
        "aap2_organization": "org-test",
        "kira_url": "https://kira.test",
        "kira_api_key": "key-123",
        "rocketchat_url": "https://chat.test",
        "rocketchat_api_auth_token": "token-abc",
        "rocketchat_api_user_id": "user-123",
        "litellm_api_base_url": "https://maas.test/v1",
        "litellm_virtual_key": "sk-test",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)


def test_analyze_endpoint_full_pipeline(mock_env, mock_ticket_payload):
    """Test POST /api/v1/analyze runs the full pipeline with mocked internals."""
    mock_aap2 = AsyncMock()
    mock_aap2.get_job.return_value = {
        "id": 42,
        "name": "Deploy Web App",
        "status": "failed",
        "summary_fields": {
            "job_template": {"id": 10, "name": "deploy-web"},
            "project": {"name": "web-project"},
            "inventory": {"name": "production"},
            "execution_environment": {"name": "Default EE"},
        },
        "playbook": "playbooks/deploy.yml",
        "started": "2026-04-15T10:00:00+00:00",
        "finished": "2026-04-15T10:05:00+00:00",
    }
    mock_aap2.get_job_stdout.return_value = "TASK [install] fatal: FAILED\n"
    mock_aap2.get_job_events.return_value = [{"event": "runner_on_failed"}]
    mock_aap2.register_webhook.return_value = 1

    mock_kira = AsyncMock()
    mock_kira.create_ticket.return_value = {"id": "ticket-uuid-123", "title": "test"}
    mock_kira.create_issue.return_value = {"id": "issue-uuid-456"}

    mock_rocketchat = AsyncMock()
    mock_rocketchat.post_message.return_value = "msg-001"

    with patch(
        "athena.agents.pipeline.run_pipeline",
        return_value=mock_ticket_payload,
    ):
        # Create a fresh FastAPI instance without lifespan to avoid initialization complexity
        from fastapi import FastAPI

        from athena.config import Settings
        from athena.routes import analyze, health, webhook

        app = FastAPI(
            title="Athena AIOps",
            description="Agentic AIOps service for AAP2 failure analysis",
            version="0.1.0",
        )
        app.include_router(health.router)
        app.include_router(webhook.router)
        app.include_router(analyze.router)

        # Set state attributes directly (matching app.py lifespan pattern)
        settings = Settings()
        app.state.settings = settings
        app.state.aap2 = mock_aap2
        app.state.kira = mock_kira
        app.state.rocketchat = mock_rocketchat

        with TestClient(app, raise_server_exceptions=True) as client:
            resp = client.post("/api/v1/analyze", json={"job_id": 42})

    assert resp.status_code == 200, f"Response: {resp.status_code} - {resp.text}"
    data = resp.json()
    assert data["ticket_id"] == "ticket-uuid-123"
    assert data["area"] == "application"
    assert data["confidence"] == 85
