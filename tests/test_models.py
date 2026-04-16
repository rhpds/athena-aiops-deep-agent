"""Tests for athena.models — Pydantic data contracts."""

import pytest
from pydantic import ValidationError

from athena.models import (
    DOMAIN_TO_KIRA_AREA,
    EnvironmentContext,
    IncidentEnvelope,
    IssuePayload,
    JobInfo,
    TicketPayload,
)


def _make_job_info(**overrides) -> dict:
    defaults = {
        "id": "42",
        "name": "Deploy Web App",
        "status": "failed",
        "template_id": "10",
        "template_name": "deploy-web",
        "project": "web-project",
        "inventory": "production",
        "execution_environment": "Default EE",
        "started_at": "2026-04-15T10:00:00Z",
        "finished_at": "2026-04-15T10:05:00Z",
    }
    defaults.update(overrides)
    return defaults


def _make_envelope(**overrides) -> dict:
    defaults = {
        "event_id": "evt-001",
        "received_at": "2026-04-15T10:05:30Z",
        "source": "aap2",
        "job": _make_job_info(),
        "artifacts": {
            "stdout": "TASK [install] fatal: FAILED",
            "error_excerpt": "No package httpd available",
            "events": [{"event": "runner_on_failed"}],
            "playbook_path": "playbooks/deploy.yml",
            "related_files": [],
        },
        "context": {
            "cluster": "prod-cluster",
            "environment": "prod",
            "namespace": "web-ns",
        },
    }
    defaults.update(overrides)
    return defaults


def test_incident_envelope_valid():
    envelope = IncidentEnvelope(**_make_envelope())
    assert envelope.job.name == "Deploy Web App"
    assert envelope.source == "aap2"


def test_incident_envelope_rejects_invalid_source():
    with pytest.raises(ValidationError):
        IncidentEnvelope(**_make_envelope(source="jenkins"))


def test_job_info_rejects_non_failed_status():
    with pytest.raises(ValidationError):
        JobInfo(**_make_job_info(status="successful"))


def test_environment_context_allows_none_fields():
    ctx = EnvironmentContext(cluster=None, environment=None, namespace=None)
    assert ctx.cluster is None


def test_ticket_payload_valid():
    payload = TicketPayload(
        title="Deploy Web App failed: missing httpd package",
        description="The playbook failed because httpd is not available in the repo.",
        area="application",
        confidence=85,
        risk="high",
        stage="production",
        recommended_action="Add httpd to the Satellite content view or fix the repo config.",
        affected_systems=["web-server-01"],
        skills=["linux", "ansible"],
        issues=[
            IssuePayload(
                title="Package httpd not found",
                description="dnf install httpd returned 'No package httpd available'",
                severity="high",
            )
        ],
    )
    assert payload.confidence == 85
    assert len(payload.issues) == 1


def test_ticket_payload_rejects_invalid_area():
    with pytest.raises(ValidationError):
        TicketPayload(
            title="t",
            description="d",
            area="ansible",  # must be Kira area, not agent domain
            confidence=50,
            risk="medium",
            stage="unknown",
            recommended_action="fix",
            affected_systems=[],
            skills=[],
            issues=[],
        )


def test_ticket_payload_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        TicketPayload(
            title="t",
            description="d",
            area="linux",
            confidence=150,
            risk="low",
            stage="dev",
            recommended_action="fix",
            affected_systems=[],
            skills=[],
            issues=[],
        )


def test_domain_to_kira_area_mapping():
    assert DOMAIN_TO_KIRA_AREA["ansible"] == "application"
    assert DOMAIN_TO_KIRA_AREA["openshift"] == "kubernetes"
    assert DOMAIN_TO_KIRA_AREA["linux"] == "linux"
    assert DOMAIN_TO_KIRA_AREA["networking"] == "networking"
