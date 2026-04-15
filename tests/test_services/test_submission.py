"""Tests for athena.services.submission — Kira + Rocket.Chat output."""

import logging
from unittest.mock import AsyncMock

import pytest

from athena.models import IssuePayload, TicketPayload
from athena.services.submission import submit_ticket


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
def mock_kira() -> AsyncMock:
    kira = AsyncMock()
    kira.create_ticket.return_value = {"id": "ticket-uuid-123", "title": "Deploy Web App failed"}
    kira.create_issue.return_value = {"id": "issue-uuid-456"}
    return kira


@pytest.fixture
def mock_rocketchat() -> AsyncMock:
    rc = AsyncMock()
    rc.post_message.return_value = "msg-001"
    return rc


async def test_submit_ticket_creates_ticket_and_issues(
    mock_kira: AsyncMock, mock_rocketchat: AsyncMock
):
    result = await submit_ticket(
        payload=_ticket(),
        kira=mock_kira,
        rocketchat=mock_rocketchat,
        kira_frontend_url="https://kira.example.com",
        rocketchat_channel="support",
        job_name="Deploy Web App",
    )

    assert result["ticket_id"] == "ticket-uuid-123"
    mock_kira.create_ticket.assert_called_once()
    mock_kira.create_issue.assert_called_once_with("ticket-uuid-123", _ticket().issues[0])


async def test_submit_ticket_posts_to_rocketchat(mock_kira: AsyncMock, mock_rocketchat: AsyncMock):
    await submit_ticket(
        payload=_ticket(),
        kira=mock_kira,
        rocketchat=mock_rocketchat,
        kira_frontend_url="https://kira.example.com",
        rocketchat_channel="support",
        job_name="Deploy Web App",
    )

    mock_rocketchat.post_message.assert_called_once()
    call_args = mock_rocketchat.post_message.call_args
    assert call_args[0][0] == "support"
    assert "Deploy Web App" in call_args[0][1]


async def test_submit_ticket_succeeds_if_rocketchat_fails(
    mock_kira: AsyncMock, mock_rocketchat: AsyncMock, caplog
):
    mock_rocketchat.post_message.side_effect = Exception("connection refused")

    with caplog.at_level(logging.WARNING):
        result = await submit_ticket(
            payload=_ticket(),
            kira=mock_kira,
            rocketchat=mock_rocketchat,
            kira_frontend_url="https://kira.example.com",
            rocketchat_channel="support",
            job_name="Deploy Web App",
        )

    # Ticket should still be created
    assert result["ticket_id"] == "ticket-uuid-123"
    assert "Rocket.Chat" in caplog.text
