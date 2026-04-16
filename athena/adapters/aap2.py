"""AAP2 Controller API client.

Wraps the AAP2 REST API for job retrieval and webhook registration.
Auth: HTTP Basic Auth.

AAP2 gateway exposes the controller API at /api/controller/v2/.
The api_prefix defaults to this but can be overridden for standalone controllers.
"""

import base64

import httpx


class AAP2Client:
    """Async client for AAP2 Controller REST API."""

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        organization: str = "",
        api_prefix: str = "/api/controller/v2",
    ):
        self._base_url = base_url.rstrip("/")
        self._api = api_prefix.rstrip("/")
        self._organization = organization
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

    async def get_job(self, job_id: int) -> dict:
        """Retrieve job metadata."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base_url}{self._api}/jobs/{job_id}/",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

    async def get_job_stdout(self, job_id: int) -> str:
        """Retrieve raw stdout text for a job."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base_url}{self._api}/jobs/{job_id}/stdout/?format=txt",
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.text

    async def get_job_events(self, job_id: int) -> list[dict]:
        """Retrieve failed events for a job."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base_url}{self._api}/jobs/{job_id}/job_events/",
                params={"event": "runner_on_failed", "page_size": 50},
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()["results"]

    async def get_job_template(self, template_id: int) -> dict:
        """Retrieve job template details."""
        async with httpx.AsyncClient() as http:
            resp = await http.get(
                f"{self._base_url}{self._api}/job_templates/{template_id}/",
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

    async def _resolve_organization_id(self, http: httpx.AsyncClient) -> int | None:
        """Resolve the organization name to its ID. Returns None if not set."""
        if not self._organization:
            return None
        resp = await http.get(
            f"{self._base_url}{self._api}/organizations/",
            params={"name": self._organization},
            headers=self._headers,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if results:
            return results[0]["id"]
        return None

    async def register_webhook(self, target_url: str) -> int:
        """Ensure a notification template exists and is attached to all job templates.

        Idempotent: if a template already points at target_url, reuses it.
        Attaches the template as a failure notification on all job templates in the org.
        Returns the template ID.
        """
        async with httpx.AsyncClient() as http:
            org_id = await self._resolve_organization_id(http)

            # Check existing templates
            resp = await http.get(
                f"{self._base_url}{self._api}/notification_templates/",
                params={"page_size": 100},
                headers=self._headers,
            )
            resp.raise_for_status()
            templates = resp.json()["results"]

            template_id = None
            for tpl in templates:
                config = tpl.get("notification_configuration", {})
                if config.get("url") == target_url:
                    template_id = tpl["id"]
                    break

            if template_id is None:
                # Create new template scoped to the user's organization
                body = {
                    "name": "athena-webhook",
                    "description": "Athena AIOps failure notification webhook",
                    "organization": org_id,
                    "notification_type": "webhook",
                    "notification_configuration": {
                        "url": target_url,
                        "http_method": "POST",
                        "headers": {"Content-Type": "application/json"},
                    },
                }
                resp = await http.post(
                    f"{self._base_url}{self._api}/notification_templates/",
                    json=body,
                    headers=self._headers,
                )
                resp.raise_for_status()
                template_id = resp.json()["id"]

            # Attach to all job templates in the org as failure notification
            await self._attach_to_job_templates(http, template_id)

            return template_id

    async def _attach_to_job_templates(
        self, http: httpx.AsyncClient, notification_template_id: int
    ) -> None:
        """Attach a notification template to all job templates as a failure notification."""
        resp = await http.get(
            f"{self._base_url}{self._api}/job_templates/",
            params={"page_size": 100},
            headers=self._headers,
        )
        resp.raise_for_status()

        for jt in resp.json().get("results", []):
            await http.post(
                f"{self._base_url}{self._api}/job_templates/{jt['id']}/"
                f"notification_templates_error/",
                json={"id": notification_template_id},
                headers=self._headers,
            )
