"""Tests for athena.adapters.aap2 — AAP2 Controller API client."""

import pytest
import pytest_httpx

from athena.adapters.aap2 import AAP2Client


@pytest.fixture
def client() -> AAP2Client:
    return AAP2Client(
        base_url="https://aap2.example.com",
        username="admin",
        password="secret",
    )


async def test_get_job(client: AAP2Client, httpx_mock: pytest_httpx.HTTPXMock):
    httpx_mock.add_response(
        url="https://aap2.example.com/api/controller/v2/jobs/42/",
        method="GET",
        json={
            "id": 42,
            "name": "Deploy Web App",
            "status": "failed",
            "summary_fields": {
                "job_template": {"id": 10, "name": "deploy-web"},
                "project": {"name": "web-project"},
                "inventory": {"name": "production"},
            },
            "execution_environment": {"name": "Default EE"},
            "started": "2026-04-15T10:00:00Z",
            "finished": "2026-04-15T10:05:00Z",
        },
    )

    job = await client.get_job(42)
    assert job["id"] == 42
    assert job["name"] == "Deploy Web App"

    request = httpx_mock.get_request()
    assert request.headers["Authorization"].startswith("Basic ")


async def test_get_job_stdout(client: AAP2Client, httpx_mock: pytest_httpx.HTTPXMock):
    httpx_mock.add_response(
        url="https://aap2.example.com/api/controller/v2/jobs/42/stdout/?format=txt",
        method="GET",
        text="TASK [install httpd] ***\nfatal: FAILED! => No package httpd available\n",
    )

    stdout = await client.get_job_stdout(42)
    assert "fatal: FAILED" in stdout


async def test_get_job_events_filters_failed(
    client: AAP2Client, httpx_mock: pytest_httpx.HTTPXMock
):
    httpx_mock.add_response(
        url="https://aap2.example.com/api/controller/v2/jobs/42/job_events/?event=runner_on_failed&page_size=50",
        method="GET",
        json={
            "results": [
                {"event": "runner_on_failed", "event_data": {"task": "install httpd"}},
            ]
        },
    )

    events = await client.get_job_events(42)
    assert len(events) == 1
    assert events[0]["event"] == "runner_on_failed"


async def test_register_webhook_creates_when_missing(
    client: AAP2Client, httpx_mock: pytest_httpx.HTTPXMock
):
    httpx_mock.add_response(
        url="https://aap2.example.com/api/controller/v2/notification_templates/?name=athena-webhook&page_size=100",
        method="GET",
        json={"results": []},
    )
    httpx_mock.add_response(
        url="https://aap2.example.com/api/controller/v2/notification_templates/",
        method="POST",
        json={"id": 1, "name": "athena-webhook"},
        status_code=201,
    )
    httpx_mock.add_response(
        url="https://aap2.example.com/api/controller/v2/job_templates/?page_size=100",
        method="GET",
        json={"results": [{"id": 10, "name": "test-jt"}]},
    )
    httpx_mock.add_response(
        url="https://aap2.example.com/api/controller/v2/job_templates/10/notification_templates_error/",
        method="POST",
        json={},
        status_code=204,
    )

    template_id = await client.register_webhook("https://athena.example.com/api/v1/webhook/aap2")
    assert template_id == 1


async def test_register_webhook_reuses_existing(
    client: AAP2Client, httpx_mock: pytest_httpx.HTTPXMock
):
    httpx_mock.add_response(
        url="https://aap2.example.com/api/controller/v2/notification_templates/?name=athena-webhook&page_size=100",
        method="GET",
        json={
            "results": [
                {
                    "id": 99,
                    "name": "athena-webhook",
                    "summary_fields": {"organization": {"id": None}},
                    "notification_configuration": {
                        "url": "https://athena.example.com/api/v1/webhook/aap2"
                    },
                }
            ]
        },
    )
    httpx_mock.add_response(
        url="https://aap2.example.com/api/controller/v2/job_templates/?page_size=100",
        method="GET",
        json={"results": []},
    )

    template_id = await client.register_webhook("https://athena.example.com/api/v1/webhook/aap2")
    assert template_id == 99
