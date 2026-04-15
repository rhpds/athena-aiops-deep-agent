"""Kira ticketing system API client.

API reference: https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml
Auth: X-API-Key header.
"""

import httpx

from athena.models import IssuePayload, TicketPayload


class KiraClient:
    """Async client for the Kira ticketing API."""

    def __init__(self, base_url: str, api_key: str):
        self._base_url = base_url.rstrip("/")
        self._headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
        }

    async def create_ticket(self, payload: TicketPayload) -> dict:
        """POST /api/v1/tickets — create a new ticket. Returns the ticket data dict."""
        body = {
            "title": payload.title,
            "description": payload.description,
            "area": payload.area,
            "confidence": payload.confidence,
            "risk": payload.risk,
            "stage": payload.stage,
            "recommended_action": payload.recommended_action,
            "affected_systems": payload.affected_systems,
            "skills": payload.skills,
            "created_by_source": "agent",
        }
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._base_url}/api/v1/tickets",
                json=body,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()["data"]

    async def create_issue(self, ticket_id: str, issue: IssuePayload) -> dict:
        """POST /api/v1/tickets/{ticket_id}/issues — attach an issue to a ticket."""
        body = {
            "title": issue.title,
            "description": issue.description,
            "severity": issue.severity,
        }
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._base_url}/api/v1/tickets/{ticket_id}/issues",
                json=body,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()["data"]

    async def upload_artifact(
        self, ticket_id: str, filename: str, content: bytes
    ) -> dict:
        """POST /api/v1/tickets/{ticket_id}/artifacts — upload a file artifact."""
        headers = {"X-API-Key": self._headers["X-API-Key"]}
        async with httpx.AsyncClient() as http:
            resp = await http.post(
                f"{self._base_url}/api/v1/tickets/{ticket_id}/artifacts",
                files={"file": (filename, content)},
                headers=headers,
            )
            resp.raise_for_status()
            return resp.json()["data"]
