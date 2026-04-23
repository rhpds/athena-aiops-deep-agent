"""Kira ticketing system API client.

API reference: https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml
Auth: X-API-Key header.

Kira expects confidence and risk as floats 0.0–1.0. Our TicketPayload uses
confidence as int 0–100 and risk as a string. This adapter handles the mapping.
"""

import logging

import httpx

from athena.models import IssuePayload, TicketPayload

logger = logging.getLogger(__name__)

# Map risk labels to 0.0–1.0 float values for Kira
RISK_TO_FLOAT = {
    "critical": 1.0,
    "high": 0.8,
    "medium": 0.5,
    "low": 0.2,
}


class KiraClient:
    """Async client for the Kira ticketing API."""

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }

    async def create_ticket(self, payload: TicketPayload) -> dict:
        """POST /api/v1/tickets — create a new ticket. Returns the ticket data."""
        body = {
            "title": payload.title,
            "description": payload.description,
            "area": payload.area,
            "confidence": payload.confidence / 100.0,  # int 0-100 → float 0.0-1.0
            "risk": RISK_TO_FLOAT.get(payload.risk, 0.5),  # label → float 0.0-1.0
            "stage": payload.stage,
            "recommended_action": payload.recommended_action,
            "affected_systems": payload.affected_systems,
            "skills": payload.skills,
            "created_by_source": "agent",
        }
        if payload.agent_name:
            body["agent_name"] = payload.agent_name
        if payload.model_name:
            body["model_name"] = payload.model_name
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._base_url}/api/v1/tickets",
                json=body,
                headers=self._headers,
            )
            if resp.status_code >= 400:
                logger.error("Kira rejected ticket: %s %s", resp.status_code, resp.text)
            resp.raise_for_status()
            return resp.json()

    async def create_issue(self, ticket_id: str, issue: IssuePayload) -> dict:
        """POST /api/v1/tickets/{ticket_id}/issues — attach an issue to a ticket."""
        body = {
            "title": issue.title,
            "description": issue.description,
            "severity": issue.severity,
            "fix": issue.fix,
        }
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._base_url}/api/v1/tickets/{ticket_id}/issues",
                json=body,
                headers=self._headers,
            )
            if resp.status_code >= 400:
                logger.error("Kira rejected issue: %s %s", resp.status_code, resp.text)
            resp.raise_for_status()
            return resp.json()

    async def upload_artifact(self, ticket_id: str, filename: str, content: bytes) -> dict:
        """POST /api/v1/tickets/{ticket_id}/artifacts — upload a file artifact."""
        headers = {"X-API-Key": self._headers["X-API-Key"]}
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._base_url}/api/v1/tickets/{ticket_id}/artifacts",
                files={"file": (filename, content)},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()
