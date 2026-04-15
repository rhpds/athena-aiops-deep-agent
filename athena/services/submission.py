"""Submit agent-produced tickets to Kira and notify via Rocket.Chat.

This is deterministic code — no LLM calls. Takes the structured
TicketPayload from the agent pipeline and handles API submission.
"""

import logging

from athena.adapters.kira import KiraClient
from athena.adapters.rocketchat import RocketChatClient
from athena.models import TicketPayload

logger = logging.getLogger(__name__)


async def submit_ticket(
    payload: TicketPayload,
    kira: KiraClient,
    rocketchat: RocketChatClient,
    kira_frontend_url: str,
    rocketchat_channel: str,
    job_name: str,
) -> dict:
    """Submit a ticket to Kira, attach issues, and notify Rocket.Chat.

    Returns dict with ticket_id and ticket_url.
    Rocket.Chat failure is non-fatal — the ticket is still considered submitted.
    """
    # Create ticket in Kira
    ticket_data = await kira.create_ticket(payload)
    ticket_id = ticket_data["id"]
    ticket_url = f"{kira_frontend_url.rstrip('/')}/tickets/{ticket_id}"

    # Attach issues
    for issue in payload.issues:
        await kira.create_issue(ticket_id, issue)

    # Notify Rocket.Chat (non-fatal)
    try:
        message = RocketChatClient.format_notification(
            job_name=job_name,
            area=payload.area,
            risk=payload.risk,
            confidence=payload.confidence,
            stage=payload.stage,
            recommended_action=payload.recommended_action,
            ticket_url=ticket_url,
        )
        await rocketchat.post_message(rocketchat_channel, message)
    except Exception:
        logger.warning("Rocket.Chat notification failed — ticket was still created", exc_info=True)

    return {"ticket_id": ticket_id, "ticket_url": ticket_url}
