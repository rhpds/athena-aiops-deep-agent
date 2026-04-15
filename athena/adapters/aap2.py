"""AAP2 Controller API client.

Wraps the AAP2 v2 REST API for job retrieval and webhook registration.
Auth: HTTP Basic Auth.
"""

import base64

import httpx


class AAP2Client:
    """Async client for AAP2 Controller REST API."""

    def __init__(self, base_url: str, username: str, password: str):
        self._base_url = base_url.rstrip("/")
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

    async def get_job(self, job_id: int) -> dict:
        """GET /api/v2/jobs/{id}/ — retrieve job metadata."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base_url}/api/v2/jobs/{job_id}/",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_job_stdout(self, job_id: int) -> str:
        """GET /api/v2/jobs/{id}/stdout/?format=txt — raw stdout text."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base_url}/api/v2/jobs/{job_id}/stdout/?format=txt",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.text

    async def get_job_events(self, job_id: int) -> list[dict]:
        """GET /api/v2/jobs/{id}/job_events/ — failed events only."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base_url}/api/v2/jobs/{job_id}/job_events/",
                params={"event": "runner_on_failed", "page_size": 50},
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()["results"]

    async def get_job_template(self, template_id: int) -> dict:
        """GET /api/v2/job_templates/{id}/ — template details."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base_url}/api/v2/job_templates/{template_id}/",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_related_artifacts(self, job_id: int) -> dict:
        """Fetch project and inventory details related to a job."""
        job = await self.get_job(job_id)
        summary = job.get("summary_fields", {})
        return {
            "playbook_path": job.get("playbook"),
            "project": summary.get("project", {}).get("name"),
            "inventory": summary.get("inventory", {}).get("name"),
        }

    async def register_webhook(self, target_url: str) -> int:
        """Ensure a notification template exists for Athena's webhook.

        Idempotent: if a template already points at target_url, returns its ID.
        Otherwise creates a new one. Returns the template ID.
        """
        async with httpx.AsyncClient() as http:
            # Check existing templates
            resp = await http.get(
                f"{self._base_url}/api/v2/notification_templates/",
                params={"page_size": 100},
                headers=self._headers,
            )
            resp.raise_for_status()
            templates = resp.json()["results"]

            for tpl in templates:
                config = tpl.get("notification_configuration", {})
                if config.get("url") == target_url:
                    return tpl["id"]

            # Create new template
            body = {
                "name": "athena-webhook",
                "description": "Athena AIOps failure notification webhook",
                "organization": None,
                "notification_type": "webhook",
                "notification_configuration": {
                    "url": target_url,
                    "http_method": "POST",
                    "headers": {"Content-Type": "application/json"},
                },
            }
            resp = await http.post(
                f"{self._base_url}/api/v2/notification_templates/",
                json=body,
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()["id"]
