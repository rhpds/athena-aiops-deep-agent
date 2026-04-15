"""Tests for athena.services.ingestion — AAP2 data normalization."""

from unittest.mock import AsyncMock

import pytest

from athena.models import IncidentEnvelope
from athena.services.ingestion import build_incident_envelope


@pytest.fixture
def mock_aap2() -> AsyncMock:
    aap2 = AsyncMock()
    aap2.get_job.return_value = {
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
        "started": "2026-04-15T10:00:00.000000+00:00",
        "finished": "2026-04-15T10:05:00.000000+00:00",
    }
    aap2.get_job_stdout.return_value = (
        "TASK [install httpd] ***\nfatal: FAILED! => No package httpd available\n"
    )
    aap2.get_job_events.return_value = [
        {"event": "runner_on_failed", "event_data": {"task": "install httpd"}}
    ]
    return aap2


async def test_build_incident_envelope(mock_aap2: AsyncMock):
    envelope = await build_incident_envelope(mock_aap2, job_id=42)

    assert isinstance(envelope, IncidentEnvelope)
    assert envelope.job.id == "42"
    assert envelope.job.name == "Deploy Web App"
    assert envelope.job.status == "failed"
    assert envelope.job.template_id == "10"
    assert envelope.job.template_name == "deploy-web"
    assert envelope.job.project == "web-project"
    assert "fatal: FAILED" in envelope.artifacts.stdout
    assert len(envelope.artifacts.events) == 1
    assert envelope.artifacts.playbook_path == "playbooks/deploy.yml"
    assert envelope.source == "aap2"


async def test_build_incident_envelope_extracts_error_excerpt(mock_aap2: AsyncMock):
    envelope = await build_incident_envelope(mock_aap2, job_id=42)
    # Error excerpt should contain the fatal line
    assert "fatal" in envelope.artifacts.error_excerpt.lower()
