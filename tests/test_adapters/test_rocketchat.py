"""Tests for athena.adapters.rocketchat — Rocket.Chat notification client."""

import pytest
import pytest_httpx

from athena.adapters.rocketchat import RocketChatClient


@pytest.fixture
def client() -> RocketChatClient:
    return RocketChatClient(
        base_url="https://chat.example.com",
        auth_token="token-abc",
        user_id="user-123",
    )


async def test_post_message_sends_correct_payload(
    client: RocketChatClient, httpx_mock: pytest_httpx.HTTPXMock
):
    httpx_mock.add_response(
        url="https://chat.example.com/api/v1/chat.postMessage",
        method="POST",
        json={"success": True, "message": {"_id": "msg-001"}},
        status_code=200,
    )

    msg_id = await client.post_message("support", "Test notification")

    assert msg_id == "msg-001"
    request = httpx_mock.get_request()
    assert request.headers["X-Auth-Token"] == "token-abc"
    assert request.headers["X-User-Id"] == "user-123"


async def test_format_ticket_notification():
    text = RocketChatClient.format_notification(
        job_name="Deploy Web App",
        area="application",
        risk="high",
        confidence=85,
        stage="production",
        recommended_action="Add httpd to the content view.",
        ticket_url="https://kira.example.com/tickets/uuid-123",
    )
    assert "Deploy Web App" in text
    assert "application" in text
    assert "high" in text
    assert "85%" in text
    assert "production" in text
    assert "https://kira.example.com/tickets/uuid-123" in text
