"""Rocket.Chat notification client.

Posts formatted messages to a channel via the Rocket.Chat REST API.
Auth: X-Auth-Token + X-User-Id headers.
"""

import httpx

RISK_EMOJI = {
    "critical": "\U0001f534",  # red circle
    "high": "\U0001f7e0",      # orange circle
    "medium": "\U0001f7e1",    # yellow circle
    "low": "\U0001f7e2",       # green circle
}


class RocketChatClient:
    """Async client for Rocket.Chat REST API."""

    def __init__(self, base_url: str, auth_token: str, user_id: str):
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "X-Auth-Token": auth_token,
            "X-User-Id": user_id,
            "Content-Type": "application/json",
        }

    async def post_message(self, channel: str, text: str) -> str:
        """Post a message to a channel. Returns the message ID."""
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._base_url}/api/v1/chat.postMessage",
                json={"channel": f"#{channel}", "text": text},
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()["message"]["_id"]

    @staticmethod
    def format_notification(
        job_name: str,
        area: str,
        risk: str,
        confidence: int,
        stage: str,
        recommended_action: str,
        ticket_url: str,
    ) -> str:
        """Format a structured notification for Rocket.Chat #support."""
        emoji = RISK_EMOJI.get(risk, "\u2753")
        return (
            f"{emoji} **{job_name}** failed "
            f"\u2014 {area} | {risk} | confidence: {confidence}% | {stage}\n"
            f"  {recommended_action}\n"
            f"  \U0001f517 {ticket_url}"
        )
