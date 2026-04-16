"""Tests for athena.adapters.kira — Kira API client."""

import httpx
import pytest
import pytest_httpx

from athena.adapters.kira import KiraClient
from athena.models import IssuePayload, TicketPayload


def _ticket() -> TicketPayload:
    return TicketPayload(
        title="Deploy Web App failed: missing httpd package",
        description="The playbook failed because httpd is not available.",
        area="application",
        confidence=85,
        risk="high",
        stage="production",
        recommended_action="Add httpd to the content view.",
        affected_systems=["web-server-01"],
        skills=["linux", "ansible"],
        issues=[
            IssuePayload(
                title="Package httpd not found",
                description="dnf returned 'No package httpd available'",
                severity="high",
            )
        ],
    )


@pytest.fixture
def client() -> KiraClient:
    return KiraClient(base_url="https://kira.example.com", api_key="test-key")


async def test_create_ticket_sends_correct_payload(
    client: KiraClient, httpx_mock: pytest_httpx.HTTPXMock
):
    httpx_mock.add_response(
        url="https://kira.example.com/api/v1/tickets",
        method="POST",
        json={
            "id": "ticket-uuid-123",
            "title": "Deploy Web App failed: missing httpd package",
        },
        status_code=201,
    )

    result = await client.create_ticket(_ticket())

    assert result["id"] == "ticket-uuid-123"
    request = httpx_mock.get_request()
    assert request.headers["X-API-Key"] == "test-key"
    assert request.headers["Content-Type"] == "application/json"
    # Verify confidence was converted to 0.0-1.0
    import json

    body = json.loads(request.content)
    assert body["confidence"] == 0.85
    assert body["risk"] == 0.8  # "high" → 0.8


async def test_create_issue_on_ticket(client: KiraClient, httpx_mock: pytest_httpx.HTTPXMock):
    httpx_mock.add_response(
        url="https://kira.example.com/api/v1/tickets/ticket-uuid-123/issues",
        method="POST",
        json={"id": "issue-uuid-456", "title": "Package httpd not found"},
        status_code=201,
    )

    issue = IssuePayload(
        title="Package httpd not found",
        description="dnf returned 'No package httpd available'",
        severity="high",
    )
    result = await client.create_issue("ticket-uuid-123", issue)

    assert result["id"] == "issue-uuid-456"


async def test_create_ticket_raises_on_error(
    client: KiraClient, httpx_mock: pytest_httpx.HTTPXMock
):
    httpx_mock.add_response(
        url="https://kira.example.com/api/v1/tickets",
        method="POST",
        json={"error": {"code": "VALIDATION_ERROR", "message": "Invalid area"}},
        status_code=422,
    )

    with pytest.raises(httpx.HTTPStatusError):
        await client.create_ticket(_ticket())
