# Athena AIOps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Athena, an agentic AIOps service that ingests AAP2 job failures via webhook, analyzes them through a Deep Agents multi-agent pipeline, and creates structured tickets in Kira with Rocket.Chat notifications.

**Architecture:** FastAPI service wrapping a Deep Agents pipeline. AAP2 webhook triggers ingestion, `ops_manager` agent classifies and delegates to specialist SRE subagents, a `reviewer` agent validates ticket quality, then deterministic Python code submits to Kira API and posts to Rocket.Chat. Deployed via Helm chart on OpenShift.

**Tech Stack:** Python 3.13, uv, FastAPI, Pydantic V2, httpx, deepagents, langchain-core, langchain-anthropic, PyYAML, Rich

**Design Spec:** `docs/superpowers/specs/2026-04-15-athena-aiops-design.md`

**Reference Kira API:** https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml

---

## File Map

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Project metadata, dependencies |
| `.gitignore` | Python ignores |
| `athena/__init__.py` | Package marker |
| `athena/__main__.py` | `python -m athena` uvicorn entrypoint |
| `athena/config.py` | Pydantic `BaseSettings` — all env vars |
| `athena/models.py` | Pydantic V2 models: `IncidentEnvelope`, `TicketPayload`, area mapping |
| `athena/app.py` | FastAPI app, lifespan (client init, webhook registration) |
| `athena/routes/health.py` | `GET /healthz`, `GET /readyz` |
| `athena/routes/webhook.py` | `POST /api/v1/webhook/aap2` |
| `athena/routes/analyze.py` | `POST /api/v1/analyze` |
| `athena/adapters/aap2.py` | AAP2 Controller async HTTP client |
| `athena/adapters/kira.py` | Kira ticketing async HTTP client |
| `athena/adapters/rocketchat.py` | Rocket.Chat async HTTP client |
| `athena/services/ingestion.py` | Normalize AAP2 data into `IncidentEnvelope` |
| `athena/services/submission.py` | Send `TicketPayload` to Kira + Rocket.Chat |
| `athena/agents/pipeline.py` | Deep Agents wiring: `create_ops_manager()`, `load_subagents()` |
| `athena/agents/tools.py` | `@tool` functions for subagents |
| `AGENTS.md` | ops_manager persona and triage protocol |
| `subagents.yaml` | Subagent definitions |
| `skills/*/SKILL.md` | Agent skill files (8 skills) |
| `templates/ticket.md.j2` | Canonical ticket markdown template |
| `Dockerfile` | Container image build |
| `deploy/helm/athena/*` | Helm chart for OpenShift deployment |
| `tests/test_models.py` | Model validation tests |
| `tests/test_adapters/test_*.py` | Adapter unit tests (mocked HTTP) |
| `tests/test_services/test_*.py` | Service logic tests |
| `tests/e2e/test_pipeline.py` | End-to-end pipeline test (mocked LLM) |

---

## Task 1: Project Scaffolding and Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `athena/__init__.py`
- Create: `athena/__main__.py`
- Create: `athena/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "athena-aiops"
version = "0.1.0"
description = "Agentic AIOps service — AAP2 failure analysis via Deep Agents"
requires-python = ">=3.13"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "httpx>=0.28",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "deepagents",
    "langchain-core",
    "langchain-anthropic",
    "langchain-openai",
    "tavily-python",
    "pyyaml",
    "rich",
    "jinja2",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25",
    "pytest-httpx>=0.35",
    "ruff>=0.8",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
target-version = "py313"
line-length = 99

[tool.ruff.lint]
select = ["E", "F", "I", "UP"]
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/
.ruff_cache/
.pytest_cache/
investigations/
.env
```

- [ ] **Step 3: Create `athena/__init__.py`**

```python
"""Athena AIOps — Agentic failure analysis for AAP2."""
```

- [ ] **Step 4: Create `athena/config.py`**

```python
"""Centralized configuration from environment variables."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All Athena configuration. Validated at startup — missing required vars cause immediate failure."""

    model_config = {"env_prefix": "", "case_sensitive": False}

    # AAP2 Controller
    aap2_url: str
    aap2_username: str
    aap2_password: SecretStr
    aap2_organization: str

    # Kira ticketing system
    kira_url: str
    kira_api_key: SecretStr

    # Rocket.Chat
    rocketchat_url: str
    rocketchat_api_auth_token: SecretStr
    rocketchat_api_user_id: str
    rocketchat_channel: str = "support"

    # MaaS (LLM gateway) — env var names are litellm_* per provisioning system
    litellm_api_base_url: str
    litellm_virtual_key: SecretStr

    # Optional
    tavily_api_key: SecretStr | None = None

    # Athena service
    athena_webhook_path: str = "/api/v1/webhook/aap2"
    athena_base_url: str | None = None
```

- [ ] **Step 5: Write failing test for config validation**

Create `tests/test_config.py`:

```python
"""Tests for athena.config."""

import pytest
from pydantic import ValidationError

from athena.config import Settings


def _minimal_env() -> dict[str, str]:
    """Minimal valid env vars for Settings."""
    return {
        "aap2_url": "https://aap2.example.com",
        "aap2_username": "admin",
        "aap2_password": "secret",
        "aap2_organization": "org-test",
        "kira_url": "https://kira.example.com",
        "kira_api_key": "key-123",
        "rocketchat_url": "https://chat.example.com",
        "rocketchat_api_auth_token": "token-abc",
        "rocketchat_api_user_id": "user-123",
        "litellm_api_base_url": "https://maas.example.com/v1",
        "litellm_virtual_key": "sk-test",
    }


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch):
    env = _minimal_env()
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    settings = Settings()
    assert settings.aap2_url == "https://aap2.example.com"
    assert settings.aap2_password.get_secret_value() == "secret"
    assert settings.rocketchat_channel == "support"
    assert settings.tavily_api_key is None


def test_settings_fails_on_missing_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("aap2_url", "https://aap2.example.com")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_optional_tavily(monkeypatch: pytest.MonkeyPatch):
    env = _minimal_env()
    env["tavily_api_key"] = "tvly-test"
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    settings = Settings()
    assert settings.tavily_api_key.get_secret_value() == "tvly-test"
```

- [ ] **Step 6: Run test to verify it passes**

```bash
uv sync
uv run pytest tests/test_config.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 7: Create `athena/__main__.py`**

```python
"""Entrypoint for `python -m athena`."""

import uvicorn


def main():
    uvicorn.run("athena.app:app", host="0.0.0.0", port=8080, reload=True)


if __name__ == "__main__":
    main()
```

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore athena/__init__.py athena/__main__.py athena/config.py tests/test_config.py
git commit -m "feat: project scaffolding with config and test infrastructure"
```

---

## Task 2: Pydantic Data Models

**Files:**
- Create: `athena/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing tests for models**

Create `tests/test_models.py`:

```python
"""Tests for athena.models — Pydantic data contracts."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from athena.models import (
    DOMAIN_TO_KIRA_AREA,
    EnvironmentContext,
    IncidentEnvelope,
    IssuePayload,
    JobArtifacts,
    JobInfo,
    TicketPayload,
)


def _make_job_info(**overrides) -> dict:
    defaults = {
        "id": "42",
        "name": "Deploy Web App",
        "status": "failed",
        "template_id": "10",
        "template_name": "deploy-web",
        "project": "web-project",
        "inventory": "production",
        "execution_environment": "Default EE",
        "started_at": "2026-04-15T10:00:00Z",
        "finished_at": "2026-04-15T10:05:00Z",
    }
    defaults.update(overrides)
    return defaults


def _make_envelope(**overrides) -> dict:
    defaults = {
        "event_id": "evt-001",
        "received_at": "2026-04-15T10:05:30Z",
        "source": "aap2",
        "job": _make_job_info(),
        "artifacts": {
            "stdout": "TASK [install] fatal: FAILED",
            "error_excerpt": "No package httpd available",
            "events": [{"event": "runner_on_failed"}],
            "playbook_path": "playbooks/deploy.yml",
            "related_files": [],
        },
        "context": {
            "cluster": "prod-cluster",
            "environment": "prod",
            "namespace": "web-ns",
        },
    }
    defaults.update(overrides)
    return defaults


def test_incident_envelope_valid():
    envelope = IncidentEnvelope(**_make_envelope())
    assert envelope.job.name == "Deploy Web App"
    assert envelope.source == "aap2"


def test_incident_envelope_rejects_invalid_source():
    with pytest.raises(ValidationError):
        IncidentEnvelope(**_make_envelope(source="jenkins"))


def test_job_info_rejects_non_failed_status():
    with pytest.raises(ValidationError):
        JobInfo(**_make_job_info(status="successful"))


def test_environment_context_allows_none_fields():
    ctx = EnvironmentContext(cluster=None, environment=None, namespace=None)
    assert ctx.cluster is None


def test_ticket_payload_valid():
    payload = TicketPayload(
        title="Deploy Web App failed: missing httpd package",
        description="The playbook failed because httpd is not available in the repo.",
        area="application",
        confidence=85,
        risk="high",
        stage="production",
        recommended_action="Add httpd to the Satellite content view or fix the repo config.",
        affected_systems=["web-server-01"],
        skills=["linux", "ansible"],
        issues=[
            IssuePayload(
                title="Package httpd not found",
                description="dnf install httpd returned 'No package httpd available'",
                severity="high",
            )
        ],
    )
    assert payload.confidence == 85
    assert len(payload.issues) == 1


def test_ticket_payload_rejects_invalid_area():
    with pytest.raises(ValidationError):
        TicketPayload(
            title="t",
            description="d",
            area="ansible",  # must be Kira area, not agent domain
            confidence=50,
            risk="medium",
            stage="unknown",
            recommended_action="fix",
            affected_systems=[],
            skills=[],
            issues=[],
        )


def test_ticket_payload_rejects_confidence_out_of_range():
    with pytest.raises(ValidationError):
        TicketPayload(
            title="t",
            description="d",
            area="linux",
            confidence=150,
            risk="low",
            stage="dev",
            recommended_action="fix",
            affected_systems=[],
            skills=[],
            issues=[],
        )


def test_domain_to_kira_area_mapping():
    assert DOMAIN_TO_KIRA_AREA["ansible"] == "application"
    assert DOMAIN_TO_KIRA_AREA["openshift"] == "kubernetes"
    assert DOMAIN_TO_KIRA_AREA["linux"] == "linux"
    assert DOMAIN_TO_KIRA_AREA["networking"] == "networking"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_models.py -v
```

Expected: FAIL — `athena.models` does not exist yet.

- [ ] **Step 3: Implement `athena/models.py`**

```python
"""Pydantic V2 data models for Athena AIOps.

Enum values for TicketPayload fields match the Kira OpenAPI spec:
https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# --- Agent domain → Kira area mapping ---

DOMAIN_TO_KIRA_AREA: dict[str, str] = {
    "ansible": "application",
    "linux": "linux",
    "openshift": "kubernetes",
    "networking": "networking",
}

# --- Incoming: normalized from AAP2 ---


class JobInfo(BaseModel):
    id: str
    name: str
    status: Literal["failed"]
    template_id: str
    template_name: str
    project: str
    inventory: str
    execution_environment: str
    started_at: datetime
    finished_at: datetime


class JobArtifacts(BaseModel):
    stdout: str
    error_excerpt: str
    events: list[dict]
    playbook_path: str | None = None
    related_files: list[str] = Field(default_factory=list)


class EnvironmentContext(BaseModel):
    cluster: str | None = None
    environment: Literal["dev", "test", "stage", "prod"] | None = None
    namespace: str | None = None


class IncidentEnvelope(BaseModel):
    event_id: str
    received_at: datetime
    source: Literal["aap2"]
    job: JobInfo
    artifacts: JobArtifacts
    context: EnvironmentContext


# --- Outgoing: agent output → Kira ---


class IssuePayload(BaseModel):
    title: str
    description: str
    severity: Literal["critical", "high", "medium", "low", "info"]


class TicketPayload(BaseModel):
    title: str
    description: str
    area: Literal["linux", "kubernetes", "networking", "application"]
    confidence: int = Field(ge=0, le=100)
    risk: Literal["critical", "high", "medium", "low"]
    stage: Literal["dev", "test", "production", "unknown"]
    recommended_action: str
    affected_systems: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    issues: list[IssuePayload] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_models.py -v
```

Expected: All 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add athena/models.py tests/test_models.py
git commit -m "feat: add Pydantic V2 data models for incident envelope and ticket payload"
```

---

## Task 3: Kira Adapter

**Files:**
- Create: `athena/adapters/__init__.py`
- Create: `athena/adapters/kira.py`
- Test: `tests/test_adapters/__init__.py`
- Test: `tests/test_adapters/test_kira.py`

- [ ] **Step 1: Create `tests/test_adapters/__init__.py` and `athena/adapters/__init__.py`**

Both empty files.

- [ ] **Step 2: Write failing tests for Kira adapter**

Create `tests/test_adapters/test_kira.py`:

```python
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
        json={"data": {"id": "ticket-uuid-123", "title": "Deploy Web App failed: missing httpd package"}},
        status_code=201,
    )

    result = await client.create_ticket(_ticket())

    assert result["id"] == "ticket-uuid-123"
    request = httpx_mock.get_request()
    assert request.headers["X-API-Key"] == "test-key"
    assert request.headers["Content-Type"] == "application/json"


async def test_create_issue_on_ticket(
    client: KiraClient, httpx_mock: pytest_httpx.HTTPXMock
):
    httpx_mock.add_response(
        url="https://kira.example.com/api/v1/tickets/ticket-uuid-123/issues",
        method="POST",
        json={"data": {"id": "issue-uuid-456", "title": "Package httpd not found"}},
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
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_adapters/test_kira.py -v
```

Expected: FAIL — `athena.adapters.kira` does not exist.

- [ ] **Step 4: Implement `athena/adapters/kira.py`**

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_adapters/test_kira.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add athena/adapters/__init__.py athena/adapters/kira.py tests/test_adapters/__init__.py tests/test_adapters/test_kira.py
git commit -m "feat: add Kira API adapter with ticket/issue creation"
```

---

## Task 4: Rocket.Chat Adapter

**Files:**
- Create: `athena/adapters/rocketchat.py`
- Test: `tests/test_adapters/test_rocketchat.py`

- [ ] **Step 1: Write failing tests for Rocket.Chat adapter**

Create `tests/test_adapters/test_rocketchat.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_adapters/test_rocketchat.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `athena/adapters/rocketchat.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_adapters/test_rocketchat.py -v
```

Expected: Both tests PASS.

- [ ] **Step 5: Commit**

```bash
git add athena/adapters/rocketchat.py tests/test_adapters/test_rocketchat.py
git commit -m "feat: add Rocket.Chat adapter with formatted notifications"
```

---

## Task 5: AAP2 Adapter

**Files:**
- Create: `athena/adapters/aap2.py`
- Test: `tests/test_adapters/test_aap2.py`

- [ ] **Step 1: Write failing tests for AAP2 adapter**

Create `tests/test_adapters/test_aap2.py`:

```python
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
        url="https://aap2.example.com/api/v2/jobs/42/",
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
        url="https://aap2.example.com/api/v2/jobs/42/stdout/?format=txt",
        method="GET",
        text="TASK [install httpd] ***\nfatal: FAILED! => No package httpd available\n",
    )

    stdout = await client.get_job_stdout(42)
    assert "fatal: FAILED" in stdout


async def test_get_job_events_filters_failed(
    client: AAP2Client, httpx_mock: pytest_httpx.HTTPXMock
):
    httpx_mock.add_response(
        url="https://aap2.example.com/api/v2/jobs/42/job_events/?event=runner_on_failed&page_size=50",
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
    # List existing templates — none match
    httpx_mock.add_response(
        url="https://aap2.example.com/api/v2/notification_templates/?page_size=100",
        method="GET",
        json={"results": []},
    )
    # Create notification template
    httpx_mock.add_response(
        url="https://aap2.example.com/api/v2/notification_templates/",
        method="POST",
        json={"id": 1, "name": "athena-webhook"},
        status_code=201,
    )

    template_id = await client.register_webhook("https://athena.example.com/api/v1/webhook/aap2")
    assert template_id == 1

    requests = httpx_mock.get_requests()
    assert len(requests) == 2
    assert requests[1].method == "POST"


async def test_register_webhook_skips_when_exists(
    client: AAP2Client, httpx_mock: pytest_httpx.HTTPXMock
):
    httpx_mock.add_response(
        url="https://aap2.example.com/api/v2/notification_templates/?page_size=100",
        method="GET",
        json={
            "results": [
                {
                    "id": 99,
                    "name": "athena-webhook",
                    "notification_configuration": {
                        "url": "https://athena.example.com/api/v1/webhook/aap2"
                    },
                }
            ]
        },
    )

    template_id = await client.register_webhook("https://athena.example.com/api/v1/webhook/aap2")
    assert template_id == 99

    # Only the GET request, no POST
    assert len(httpx_mock.get_requests()) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_adapters/test_aap2.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `athena/adapters/aap2.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_adapters/test_aap2.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add athena/adapters/aap2.py tests/test_adapters/test_aap2.py
git commit -m "feat: add AAP2 Controller adapter with webhook registration"
```

---

## Task 6: Ingestion Service

**Files:**
- Create: `athena/services/__init__.py`
- Create: `athena/services/ingestion.py`
- Test: `tests/test_services/__init__.py`
- Test: `tests/test_services/test_ingestion.py`

- [ ] **Step 1: Create `__init__.py` files**

Create empty `athena/services/__init__.py` and `tests/test_services/__init__.py`.

- [ ] **Step 2: Write failing tests for ingestion service**

Create `tests/test_services/test_ingestion.py`:

```python
"""Tests for athena.services.ingestion — AAP2 data normalization."""

from unittest.mock import AsyncMock

import pytest

from athena.models import IncidentEnvelope
from athena.services.ingestion import build_incident_envelope


@pytest.fixture
def mock_aap2() -> AsyncMock:
    aap2 = AsyncMock()
    aap2.get_job.return_value = {
        "id": 42,
        "name": "Deploy Web App",
        "status": "failed",
        "summary_fields": {
            "job_template": {"id": 10, "name": "deploy-web"},
            "project": {"name": "web-project"},
            "inventory": {"name": "production"},
            "execution_environment": {"name": "Default EE"},
        },
        "playbook": "playbooks/deploy.yml",
        "started": "2026-04-15T10:00:00.000000+00:00",
        "finished": "2026-04-15T10:05:00.000000+00:00",
    }
    aap2.get_job_stdout.return_value = (
        "TASK [install httpd] ***\nfatal: FAILED! => No package httpd available\n"
    )
    aap2.get_job_events.return_value = [
        {"event": "runner_on_failed", "event_data": {"task": "install httpd"}}
    ]
    return aap2


async def test_build_incident_envelope(mock_aap2: AsyncMock):
    envelope = await build_incident_envelope(mock_aap2, job_id=42)

    assert isinstance(envelope, IncidentEnvelope)
    assert envelope.job.id == "42"
    assert envelope.job.name == "Deploy Web App"
    assert envelope.job.status == "failed"
    assert envelope.job.template_id == "10"
    assert envelope.job.template_name == "deploy-web"
    assert envelope.job.project == "web-project"
    assert "fatal: FAILED" in envelope.artifacts.stdout
    assert len(envelope.artifacts.events) == 1
    assert envelope.artifacts.playbook_path == "playbooks/deploy.yml"
    assert envelope.source == "aap2"


async def test_build_incident_envelope_extracts_error_excerpt(mock_aap2: AsyncMock):
    envelope = await build_incident_envelope(mock_aap2, job_id=42)
    # Error excerpt should contain the fatal line
    assert "fatal" in envelope.artifacts.error_excerpt.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
uv run pytest tests/test_services/test_ingestion.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 4: Implement `athena/services/ingestion.py`**

```python
"""Normalize AAP2 job data into an IncidentEnvelope.

Calls the AAP2 adapter to retrieve job metadata, stdout, and events,
then builds a validated IncidentEnvelope Pydantic model.
"""

import re
import uuid
from datetime import datetime, timezone

from athena.adapters.aap2 import AAP2Client
from athena.models import (
    EnvironmentContext,
    IncidentEnvelope,
    JobArtifacts,
    JobInfo,
)


def _extract_error_excerpt(stdout: str) -> str:
    """Pull the most relevant error lines from AAP2 job stdout."""
    lines = stdout.splitlines()
    error_lines = []
    for i, line in enumerate(lines):
        if re.search(r"fatal:|FAILED|ERROR|error:", line, re.IGNORECASE):
            # Grab the error line and up to 2 lines of context after
            error_lines.extend(lines[i : i + 3])
    if error_lines:
        return "\n".join(error_lines[:10])
    # Fallback: last 10 lines
    return "\n".join(lines[-10:])


async def build_incident_envelope(
    aap2: AAP2Client, job_id: int
) -> IncidentEnvelope:
    """Fetch all job data from AAP2 and build an IncidentEnvelope."""
    job_data = await aap2.get_job(job_id)
    stdout = await aap2.get_job_stdout(job_id)
    events = await aap2.get_job_events(job_id)

    summary = job_data.get("summary_fields", {})
    jt = summary.get("job_template", {})
    ee = summary.get("execution_environment", {})

    job_info = JobInfo(
        id=str(job_data["id"]),
        name=job_data["name"],
        status="failed",
        template_id=str(jt.get("id", "")),
        template_name=jt.get("name", ""),
        project=summary.get("project", {}).get("name", ""),
        inventory=summary.get("inventory", {}).get("name", ""),
        execution_environment=ee.get("name", ""),
        started_at=job_data["started"],
        finished_at=job_data["finished"],
    )

    artifacts = JobArtifacts(
        stdout=stdout,
        error_excerpt=_extract_error_excerpt(stdout),
        events=events,
        playbook_path=job_data.get("playbook"),
        related_files=[],
    )

    context = EnvironmentContext(
        cluster=None,
        environment=None,
        namespace=None,
    )

    return IncidentEnvelope(
        event_id=str(uuid.uuid4()),
        received_at=datetime.now(timezone.utc),
        source="aap2",
        job=job_info,
        artifacts=artifacts,
        context=context,
    )
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/test_services/test_ingestion.py -v
```

Expected: Both tests PASS.

- [ ] **Step 6: Commit**

```bash
git add athena/services/__init__.py athena/services/ingestion.py tests/test_services/__init__.py tests/test_services/test_ingestion.py
git commit -m "feat: add ingestion service to normalize AAP2 jobs into IncidentEnvelope"
```

---

## Task 7: Submission Service

**Files:**
- Create: `athena/services/submission.py`
- Test: `tests/test_services/test_submission.py`

- [ ] **Step 1: Write failing tests for submission service**

Create `tests/test_services/test_submission.py`:

```python
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


async def test_submit_ticket_posts_to_rocketchat(
    mock_kira: AsyncMock, mock_rocketchat: AsyncMock
):
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_services/test_submission.py -v
```

Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement `athena/services/submission.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_services/test_submission.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add athena/services/submission.py tests/test_services/test_submission.py
git commit -m "feat: add submission service for Kira ticket creation and Rocket.Chat notification"
```

---

## Task 8: Skills and Agent Configuration Files

**Files:**
- Create: `AGENTS.md`
- Create: `subagents.yaml`
- Create: `skills/error-classifier/SKILL.md`
- Create: `skills/analyze-ansible-failure/SKILL.md`
- Create: `skills/analyze-linux-failure/SKILL.md`
- Create: `skills/analyze-openshift-failure/SKILL.md`
- Create: `skills/analyze-networking-failure/SKILL.md`
- Create: `skills/create-ticket/SKILL.md`
- Create: `skills/review-ticket/SKILL.md`
- Create: `skills/common/log-analysis/SKILL.md`
- Create: `templates/ticket.md.j2`

No tests for this task — these are configuration/content files consumed by the Deep Agents framework.

- [ ] **Step 1: Create `AGENTS.md`**

```markdown
# Athena Ops Manager

You are an experienced AI-powered operations manager specializing in AAP2 (Ansible Automation Platform 2) failure analysis. You triage failed automation jobs by classifying the failure domain and delegating to the right specialist SRE subagent.

## Role

- Receive normalized incident envelopes from failed AAP2 jobs
- Classify the failure domain using the error-classifier skill
- Delegate to the appropriate SRE subagent using the `task` tool
- Send the specialist's analysis to the reviewer subagent for quality validation
- Return the final TicketPayload as structured JSON output

## Triage Protocol

1. **Read** the incident envelope (incident.json) — review the error excerpt, stdout, and job metadata
2. **Classify** using the error-classifier skill — determine domain (ansible, linux, openshift, networking) with confidence and rationale
3. **Delegate** to the matching SRE subagent via the `task` tool with a clear description of what to analyze
4. **Review** by delegating the specialist's output to the reviewer subagent
5. **Return** the final TicketPayload JSON incorporating any reviewer amendments

## Escalation Rules

- If error-classifier confidence < 50%: still delegate to the best-guess specialist, but set risk to "high" and add "Low classification confidence — manual review recommended" to the description
- If the reviewer returns "escalate": set risk to "high" and prepend "REVIEWER ESCALATION: " to the description with the reviewer's reason
- Never return without a TicketPayload — even uncertain analyses produce a ticket for human review

## Output Contract

Always return a valid TicketPayload JSON with these fields:
- title (string, < 100 chars)
- description (string — include evidence and root cause analysis)
- area (one of: linux, kubernetes, networking, application)
- confidence (integer 0-100)
- risk (one of: critical, high, medium, low)
- stage (one of: dev, test, production, unknown)
- recommended_action (string — specific, actionable)
- affected_systems (list of strings)
- skills (list of strings — expertise areas needed)
- issues (list of {title, description, severity} objects)

## Domain Awareness

- **sre_ansible**: Playbook/role/collection errors, credential issues, execution environment problems, variable resolution, job template misconfiguration
- **sre_linux**: Package manager (dnf/yum), systemd services, SELinux, filesystem/permissions, Satellite content
- **sre_openshift**: Pod lifecycle, image pull, RBAC, operators, namespace/quota, routes/services
- **sre_networking**: DNS, SSH connectivity, proxy/TLS, routing, firewall, host unreachable

## Area Mapping

When setting the `area` field in the TicketPayload, use Kira's area values:
- ansible domain → "application"
- linux domain → "linux"
- openshift domain → "kubernetes"
- networking domain → "networking"

## Communication Style

- Be direct and precise
- Include specific evidence from the job output
- State confidence levels clearly
- Distinguish between confirmed root cause and suspected root cause
```

- [ ] **Step 2: Create `subagents.yaml`**

```yaml
sre_ansible:
  description: >
    Ansible/AAP2 specialist. Delegate automation failures: playbook syntax,
    role/collection errors, credential issues, execution environment problems,
    variable resolution, job template misconfiguration.
  model: openai/claude-sonnet-4-6
  system_prompt: |
    You are a senior Ansible and AAP2 SRE. You receive incident data from failed
    AAP2 jobs and perform root-cause analysis on automation-related failures.

    Always:
    - Read the incident context (incident.json) first
    - Identify the exact failing task, role, and module
    - Check for credential, collection, or execution environment issues
    - Reference Ansible/AAP2 docs for module behavior
    - Provide specific, actionable recommendations

    Use the create-ticket skill to structure your analysis as a TicketPayload.
    Set area to "application" for all Ansible-domain issues.
  tools:
    - web_search
  skills:
    - ./skills/analyze-ansible-failure/
    - ./skills/create-ticket/
    - ./skills/common/

sre_linux:
  description: >
    Linux specialist. Delegate host-level failures: package manager (dnf/yum),
    systemd services, SELinux, filesystem/permissions, Satellite content issues.
  model: openai/claude-sonnet-4-6
  system_prompt: |
    You are a senior Linux SRE. You receive incident data from failed AAP2 jobs
    and perform root-cause analysis on host-level Linux issues.

    Always:
    - Read the incident context (incident.json) first
    - Check for package manager errors, repo access issues
    - Look for systemd unit failures, SELinux denials, permission issues
    - Consider Satellite content view configuration for package availability
    - Provide specific commands and config changes as recommendations

    Use the create-ticket skill to structure your analysis as a TicketPayload.
    Set area to "linux" for all Linux-domain issues.
  tools:
    - web_search
  skills:
    - ./skills/analyze-linux-failure/
    - ./skills/create-ticket/
    - ./skills/common/

sre_openshift:
  description: >
    OpenShift/Kubernetes specialist. Delegate cluster failures: pod scheduling,
    image pull, RBAC, operator lifecycle, namespace/quota, routes/services.
  model: openai/claude-sonnet-4-6
  system_prompt: |
    You are a senior OpenShift/Kubernetes SRE. You receive incident data from
    failed AAP2 jobs and perform root-cause analysis on cluster-related issues.

    Always:
    - Read the incident context (incident.json) first
    - Check for pod lifecycle issues (CrashLoopBackOff, ImagePullBackOff)
    - Look for RBAC/service account problems, resource limits, quota exhaustion
    - Consider operator and CRD issues
    - Reference upstream Kubernetes docs for version-specific behavior

    Use the create-ticket skill to structure your analysis as a TicketPayload.
    Set area to "kubernetes" for all OpenShift-domain issues.
  tools:
    - web_search
  skills:
    - ./skills/analyze-openshift-failure/
    - ./skills/create-ticket/
    - ./skills/common/

sre_networking:
  description: >
    Networking specialist. Delegate connectivity failures: DNS resolution,
    SSH timeouts, proxy/TLS issues, routing, firewall rules, unreachable hosts.
  model: openai/claude-sonnet-4-6
  system_prompt: |
    You are a senior network engineer. You receive incident data from failed
    AAP2 jobs and perform root-cause analysis on connectivity issues.

    Always:
    - Read the incident context (incident.json) first
    - Work bottom-up: DNS, routing, firewall, TLS
    - Check for SSH connectivity issues (timeout, key rejection, port blocked)
    - Consider proxy configuration and certificate errors
    - Verify host reachability patterns

    Use the create-ticket skill to structure your analysis as a TicketPayload.
    Set area to "networking" for all networking-domain issues.
  tools:
    - web_search
  skills:
    - ./skills/analyze-networking-failure/
    - ./skills/create-ticket/
    - ./skills/common/

reviewer:
  description: >
    Quality reviewer. Validates ticket analysis for coherence, confidence
    justification, and actionable recommendations before submission.
  model: openai/claude-3-5-haiku
  system_prompt: |
    You review incident tickets produced by SRE specialists analyzing AAP2 job
    failures. Your job is quality assurance — not re-analysis.

    Use the review-ticket skill checklist to validate the ticket.

    Return one of:
    - "approved" with optional amendments (corrections to fields)
    - "escalate" with a specific reason why the analysis is inadequate

    Be concise. Do not re-do the analysis — only validate it.
  tools: []
  skills:
    - ./skills/review-ticket/
```

- [ ] **Step 3: Create skill files**

Create `skills/error-classifier/SKILL.md`:

```markdown
# Error Classifier

Classify the failure domain from an AAP2 job failure incident.

## Workflow

1. **Read** the error excerpt and stdout from the incident envelope
2. **Scan** for domain-specific signals:
   - **Ansible**: task/role/play references, module errors, collection not found, credential failures, "ansible" in paths, jinja2 template errors, variable undefined
   - **Linux**: dnf/yum errors, systemd unit failures, SELinux denials (avc:), permission denied on files, filesystem full/mount errors, kernel messages
   - **OpenShift/Kubernetes**: pod/container/image references, CrashLoopBackOff, ImagePullBackOff, RBAC denied, namespace/quota errors, operator errors, kubectl/oc output
   - **Networking**: DNS resolution failed, connection refused/timeout, SSH errors, TLS/SSL certificate errors, proxy errors, "unreachable" hosts, port binding failures
3. **Resolve** ambiguity: if signals span multiple domains, identify the root cause domain. Example: "Ansible task failed because DNS lookup timed out" → networking (not ansible)
4. **Emit** classification:
   - `domain`: one of ansible, linux, openshift, networking
   - `confidence`: 0-100 based on signal strength
   - `rationale`: one sentence explaining why this domain was chosen
```

Create `skills/analyze-ansible-failure/SKILL.md`:

```markdown
# Analyze Ansible Failure

Deep analysis of AAP2 job failures caused by Ansible automation issues.

## Workflow

1. **Read** the full incident context: stdout, events, job template, playbook path
2. **Identify** the failing task:
   - Which play, role, and task failed?
   - What module was used?
   - What were the module arguments (if visible)?
3. **Classify** the sub-category:
   - Syntax error in playbook/role
   - Collection or module not found / not installed in EE
   - Credential or authentication failure (vault, machine credential, cloud credential)
   - Execution environment missing required packages or collections
   - Variable undefined or incorrectly resolved (hostvars, group_vars, extra_vars)
   - Job template parameter misconfiguration (wrong inventory, limit, tags)
4. **Determine root cause** with specific evidence from the logs
5. **Assess risk**: critical (production automation broken), high (degraded automation), medium (non-prod), low (cosmetic/warning)
6. **Assess confidence**: based on evidence clarity — explicit error messages = high, ambiguous logs = lower
7. **Recommend** specific actions: exact files to edit, collections to install, credentials to update, EE to rebuild
8. **List** affected systems by name from the inventory/job output
```

Create `skills/analyze-linux-failure/SKILL.md`:

```markdown
# Analyze Linux Failure

Deep analysis of AAP2 job failures caused by host-level Linux issues.

## Workflow

1. **Read** the full incident context: stdout, events, job metadata
2. **Identify** the Linux subsystem involved:
   - Package management (dnf/yum): repo access, dependency conflicts, missing packages, Satellite content view gaps
   - Service management (systemd): unit failed to start/enable, dependency issues, restart loops
   - SELinux: AVC denials, wrong context, boolean not set, policy missing
   - Filesystem: disk full, mount failures, permission denied, ownership wrong
   - User/group: missing user, incorrect group membership, home directory issues
3. **Determine root cause** by correlating the Ansible error output with the underlying Linux issue
4. **Assess risk and confidence** based on evidence
5. **Recommend** specific actions:
   - For package issues: exact package names, repo to enable, Satellite content view to update
   - For service issues: systemctl commands, unit file changes, dependency resolution
   - For SELinux: semanage/setsebool commands, context corrections
   - For filesystem: space cleanup, mount options, chown/chmod commands
6. **List** affected hosts from the job output
```

Create `skills/analyze-openshift-failure/SKILL.md`:

```markdown
# Analyze OpenShift Failure

Deep analysis of AAP2 job failures caused by OpenShift/Kubernetes cluster issues.

## Workflow

1. **Read** the full incident context: stdout, events, job metadata
2. **Identify** the cluster component involved:
   - Pod lifecycle: CrashLoopBackOff, ImagePullBackOff, Pending, OOMKilled, Init container failures
   - Image/registry: pull errors, auth failures, image not found, registry unreachable
   - RBAC: forbidden, service account missing permissions, role binding gaps
   - Resources: quota exceeded, limit range violations, insufficient CPU/memory
   - Operators: CRD not found, operator degraded, subscription issues
   - Networking: route misconfiguration, service selector mismatch, ingress issues
3. **Determine root cause** from the Ansible k8s/oc module output and any kubectl/oc command results in the logs
4. **Assess risk and confidence** based on evidence
5. **Recommend** specific actions:
   - For pod issues: kubectl/oc commands to inspect, resource limit adjustments
   - For RBAC: exact role/rolebinding YAML to apply
   - For quota: resource quota adjustments or cleanup commands
   - For operators: subscription fixes, CRD installation commands
6. **List** affected namespaces, deployments, and pods from the output
```

Create `skills/analyze-networking-failure/SKILL.md`:

```markdown
# Analyze Networking Failure

Deep analysis of AAP2 job failures caused by network connectivity issues.

## Workflow

1. **Read** the full incident context: stdout, events, job metadata
2. **Identify** the networking layer involved:
   - DNS: resolution failures, NXDOMAIN, timeout, wrong resolver
   - SSH: connection timeout, key rejected, port closed, host key verification failed
   - TLS/SSL: certificate expired, untrusted CA, hostname mismatch, protocol version
   - Proxy: proxy authentication failed, proxy unreachable, CONNECT tunnel failure
   - Routing: host unreachable, no route to host, network unreachable
   - Firewall: connection refused on specific ports, ICMP blocked
3. **Determine root cause** — is this a client-side config issue, server-side, or infrastructure?
4. **Assess risk and confidence** based on evidence
5. **Recommend** specific actions:
   - For DNS: check resolv.conf, dig/nslookup commands, DNS server config
   - For SSH: ssh-keygen commands, known_hosts fixes, firewall port checks
   - For TLS: certificate inspection commands, CA bundle updates
   - For proxy: proxy environment variable corrections, proxy config
   - For routing/firewall: ip route commands, firewall-cmd/iptables rules
6. **List** affected hosts and network paths from the output
```

Create `skills/create-ticket/SKILL.md`:

```markdown
# Create Ticket

Structure your analysis output as a TicketPayload for submission to Kira.

## Required Fields

1. **title**: Clear, concise (< 100 chars). Format: "<What failed>: <Why it failed>". Example: "Deploy Web App failed: missing httpd package in content view"
2. **description**: Include these sections:
   - **Summary**: One paragraph explaining what happened
   - **Evidence**: Specific log lines, error messages, command output that support the diagnosis
   - **Root Cause**: What specifically caused the failure and why
   - **Impact**: What is affected and how severely
3. **area**: One of: linux, kubernetes, networking, application (use Kira's area values, not agent domain names)
4. **confidence**: 0-100. Justify it:
   - 80-100: Explicit error message directly identifies the cause
   - 60-79: Strong circumstantial evidence, likely cause
   - 40-59: Multiple possible causes, best guess
   - 0-39: Insufficient evidence, needs investigation
5. **risk**: Based on actual impact:
   - critical: Production service down or data loss
   - high: Production degraded or critical automation broken
   - medium: Non-production affected or limited impact
   - low: Cosmetic or informational
6. **stage**: dev, test, production, or unknown — based on the environment context
7. **recommended_action**: Specific and actionable. Include exact commands, file paths, or config changes. Never say "investigate further" without specifying what to investigate.
8. **affected_systems**: List system names from the job output (hostnames, services, namespaces)
9. **skills**: List expertise areas needed to resolve (e.g., ["ansible", "linux"], ["kubernetes", "networking"])
10. **issues**: Create a sub-issue for each distinct problem found. Each has title, description, severity.
```

Create `skills/review-ticket/SKILL.md`:

```markdown
# Review Ticket

Validate a ticket produced by an SRE specialist before submission.

## Checklist

1. **Title quality**: Is it specific? Reject generic titles like "Job failed" or "Error occurred". Good titles name what failed and why.
2. **Evidence present**: Does the description contain actual log lines or error messages? Reject descriptions that make claims without evidence.
3. **Confidence justified**: Is the confidence score consistent with the evidence? Flag scores > 80 that lack clear error messages. Flag scores < 40 that have clear error messages.
4. **Risk calibrated**: Does the risk level match the described impact? A non-prod failure shouldn't be "critical". A production outage shouldn't be "low".
5. **Actions actionable**: Are recommended actions specific? Reject vague advice like "check the configuration" without saying which configuration and what to check.
6. **Internal consistency**: Do the root cause, recommendations, and issues tell the same story? Flag contradictions.
7. **Completeness**: Are affected_systems populated? Are skills listed? Are issues created for each distinct problem?

## Output

Return one of:
- **approved**: The ticket meets quality standards. Optionally include amendments — specific field corrections to apply (e.g., "change confidence from 90 to 70 because the error message is ambiguous").
- **escalate**: The ticket does not meet quality standards. Include a specific reason (e.g., "description contains no evidence from logs — only assertions").
```

Create `skills/common/log-analysis/SKILL.md`:

```markdown
# Log Analysis

Shared skill for parsing Ansible/AAP2 job output. Use this before domain-specific analysis.

## Workflow

1. **Identify task boundaries**: Ansible stdout uses `TASK [name] ***` markers. Find the failing task.
2. **Extract the failing task**: Note the task name, the role it belongs to, and the play.
3. **Isolate the error**: Look for `fatal:`, `FAILED!`, `ERROR`, or `msg:` lines within the task output.
4. **Capture the error detail**: The JSON block after `=> ` contains structured error data (msg, rc, stderr, stdout).
5. **Note preceding warnings**: Lines with `[WARNING]` before the failure may provide context (e.g., deprecation, missing file).
6. **Identify patterns**: Multiple hosts failing the same task suggests an environmental issue. One host failing suggests a host-specific issue.
7. **Check for stack traces**: Python tracebacks indicate module bugs or environment issues. Note the exception type and message.

## AAP2 Stdout Structure

```
PLAY [play name] ***
TASK [Gathering Facts] ***
ok: [host1]
TASK [role : task name] ***
fatal: [host1]: FAILED! => {"changed": false, "msg": "error detail here", "rc": 1}
```

The most important information is in the `FAILED! => {...}` JSON block.
```

- [ ] **Step 4: Create `templates/ticket.md.j2`**

```jinja2
# Incident Ticket: {{ title }}

**Area:** {{ area }}
**Risk:** {{ risk }}
**Confidence:** {{ confidence }}%
**Stage:** {{ stage }}

## Description

{{ description }}

## Recommended Action

{{ recommended_action }}

## Affected Systems

{% for system in affected_systems %}- {{ system }}
{% endfor %}

## Issues

{% for issue in issues %}### {{ issue.title }} ({{ issue.severity }})

{{ issue.description }}

{% endfor %}

## Required Skills

{% for skill in skills %}- {{ skill }}
{% endfor %}
```

- [ ] **Step 5: Commit**

```bash
git add AGENTS.md subagents.yaml skills/ templates/
git commit -m "feat: add agent configuration, skills, and ticket template"
```

---

## Task 9: Agent Pipeline

**Files:**
- Create: `athena/agents/__init__.py`
- Create: `athena/agents/tools.py`
- Create: `athena/agents/pipeline.py`

This task creates the Deep Agents wiring. Tests for the pipeline are in Task 11 (e2e) because the pipeline integrates the entire agent stack and is most effectively tested end-to-end with mocked LLM responses.

- [ ] **Step 1: Create `athena/agents/__init__.py`**

Empty file.

- [ ] **Step 2: Create `athena/agents/tools.py`**

```python
"""Tool functions available to SRE subagents.

These are @tool-decorated functions registered in subagents.yaml
and resolved by load_subagents() in pipeline.py.
"""

import os
from typing import Literal

from langchain_core.tools import tool


@tool
def web_search(
    query: str,
    max_results: int = 5,
    topic: Literal["general", "news"] = "general",
) -> dict:
    """Search the web for documentation, CVEs, or troubleshooting guides.

    Args:
        query: Specific search query (be detailed)
        max_results: Number of results to return (default: 5)
        topic: "general" for docs/guides, "news" for recent incidents/CVEs

    Returns:
        Search results with titles, URLs, and content excerpts.
    """
    try:
        from tavily import TavilyClient

        api_key = os.environ.get("TAVILY_API_KEY")
        if not api_key:
            return {"error": "TAVILY_API_KEY not set — web search unavailable"}

        client = TavilyClient(api_key=api_key)
        return client.search(query, max_results=max_results, topic=topic)
    except Exception as e:
        return {"error": f"Search failed: {e}"}
```

- [ ] **Step 3: Create `athena/agents/pipeline.py`**

```python
"""Deep Agents pipeline — creates and runs the ops_manager agent.

Wires together:
- AGENTS.md as persistent memory (ops_manager persona)
- subagents.yaml as specialist SRE subagent definitions
- skills/ directories loaded per-subagent via SkillsMiddleware
- FilesystemBackend for incident context and ticket artifacts
"""

import json
import logging
from pathlib import Path

import yaml
from langchain_core.messages import AIMessage

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend

from athena.agents.tools import web_search
from athena.config import Settings
from athena.models import DOMAIN_TO_KIRA_AREA, IncidentEnvelope, TicketPayload

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent  # repo root


def load_subagents(config_path: Path) -> list[dict]:
    """Load subagent definitions from YAML and resolve tool references."""
    available_tools = {
        "web_search": web_search,
    }

    with open(config_path) as f:
        config = yaml.safe_load(f)

    subagents = []
    for name, spec in config.items():
        subagent = {
            "name": name,
            "description": spec["description"],
            "system_prompt": spec["system_prompt"],
        }
        if "model" in spec:
            subagent["model"] = spec["model"]
        if "tools" in spec:
            subagent["tools"] = [available_tools[t] for t in spec["tools"]]
        if "skills" in spec:
            subagent["skills"] = spec["skills"]
        subagents.append(subagent)

    return subagents


def create_ops_manager(settings: Settings):
    """Create the ops_manager Deep Agent configured by filesystem files.

    The MaaS gateway (OpenAI-compatible) is configured via environment variables:
    - OPENAI_API_BASE / OPENAI_BASE_URL → litellm_api_base_url
    - OPENAI_API_KEY → litellm_virtual_key
    These are set in app.py lifespan before this function is called.
    """
    return create_deep_agent(
        memory=["./AGENTS.md"],
        tools=[],
        subagents=load_subagents(PROJECT_DIR / "subagents.yaml"),
        backend=FilesystemBackend(root_dir=PROJECT_DIR),
    )


async def run_pipeline(
    envelope: IncidentEnvelope, settings: Settings
) -> TicketPayload:
    """Run the full agent pipeline on an incident.

    1. Write incident context to filesystem
    2. Invoke ops_manager agent
    3. Parse structured TicketPayload from agent output
    """
    # Write incident context for agents to read
    incident_path = PROJECT_DIR / "incident.json"
    incident_path.write_text(envelope.model_dump_json(indent=2))

    # Create and run the agent
    agent = create_ops_manager(settings)

    incident_summary = (
        f"A failed AAP2 job requires analysis.\n\n"
        f"Job: {envelope.job.name} (ID: {envelope.job.id})\n"
        f"Template: {envelope.job.template_name}\n"
        f"Project: {envelope.job.project}\n"
        f"Inventory: {envelope.job.inventory}\n\n"
        f"Error excerpt:\n{envelope.artifacts.error_excerpt}\n\n"
        f"Read incident.json for full context. "
        f"Classify the failure, delegate to the right specialist, "
        f"have the reviewer validate, and return a TicketPayload JSON."
    )

    final_message = None
    async for chunk in agent.astream(
        {"messages": [("user", incident_summary)]},
        config={"configurable": {"thread_id": f"incident-{envelope.event_id}"}},
        stream_mode="values",
    ):
        if "messages" in chunk:
            messages = chunk["messages"]
            if messages:
                last = messages[-1]
                if isinstance(last, AIMessage) and last.content:
                    final_message = last

    if not final_message:
        raise RuntimeError("Agent pipeline produced no output")

    # Extract structured output from the final message
    content = final_message.content
    if isinstance(content, list):
        text_parts = [
            p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
        ]
        content = "\n".join(text_parts)

    # Parse JSON from the agent response
    ticket_data = _extract_json(content)
    return TicketPayload(**ticket_data)


def _extract_json(text: str) -> dict:
    """Extract a JSON object from agent text output.

    Handles both raw JSON and JSON inside markdown code blocks.
    """
    import re

    # Try markdown code block first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Try raw JSON
    # Find the first { and last } for a top-level object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError(f"Could not extract JSON from agent output: {text[:200]}")
```

- [ ] **Step 4: Commit**

```bash
git add athena/agents/__init__.py athena/agents/tools.py athena/agents/pipeline.py
git commit -m "feat: add Deep Agents pipeline with ops_manager and subagent loading"
```

---

## Task 10: FastAPI Application and Routes

**Files:**
- Create: `athena/routes/__init__.py`
- Create: `athena/routes/health.py`
- Create: `athena/routes/webhook.py`
- Create: `athena/routes/analyze.py`
- Create: `athena/app.py`

- [ ] **Step 1: Create `athena/routes/__init__.py`**

Empty file.

- [ ] **Step 2: Create `athena/routes/health.py`**

```python
"""Health check endpoints for Kubernetes probes."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

# Set by app lifespan once AAP2 connection is verified and webhook registered
_ready = False


def set_ready(ready: bool):
    global _ready
    _ready = ready


@router.get("/healthz")
async def healthz():
    """Liveness probe — always returns 200 if the process is running."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz():
    """Readiness probe — returns 200 only when AAP2 webhook is registered."""
    if _ready:
        return {"status": "ready"}
    return JSONResponse(content={"status": "not ready"}, status_code=503)
```

- [ ] **Step 3: Create `athena/routes/webhook.py`**

```python
"""AAP2 webhook receiver — POST /api/v1/webhook/aap2."""

import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response

from athena.services.ingestion import build_incident_envelope
from athena.services.submission import submit_ticket

router = APIRouter()
logger = logging.getLogger(__name__)


async def _process_webhook(job_id: int, app_state: dict):
    """Background task: ingest, analyze, submit."""
    from athena.agents.pipeline import run_pipeline

    try:
        envelope = await build_incident_envelope(app_state["aap2"], job_id=job_id)
        ticket_payload = await run_pipeline(envelope, app_state["settings"])
        await submit_ticket(
            payload=ticket_payload,
            kira=app_state["kira"],
            rocketchat=app_state["rocketchat"],
            kira_frontend_url=app_state["settings"].kira_url,
            rocketchat_channel=app_state["settings"].rocketchat_channel,
            job_name=envelope.job.name,
        )
        logger.info("Ticket created for job %s", job_id)
    except Exception:
        logger.exception("Pipeline failed for job %s", job_id)


@router.post("/api/v1/webhook/aap2", status_code=202)
async def receive_webhook(
    request: Request, background_tasks: BackgroundTasks
):
    """Receive AAP2 notification webhook and process asynchronously."""
    body = await request.json()

    # AAP2 webhook payload contains job ID in various formats
    job_id = body.get("id") or body.get("job", {}).get("id")
    if not job_id:
        return Response(content="Missing job ID in payload", status_code=400)

    background_tasks.add_task(_process_webhook, int(job_id), request.app.state._state)
    return {"status": "accepted", "job_id": job_id}
```

- [ ] **Step 4: Create `athena/routes/analyze.py`**

```python
"""Manual analysis trigger — POST /api/v1/analyze."""

import logging

from fastapi import APIRouter, Request
from pydantic import BaseModel

from athena.agents.pipeline import run_pipeline
from athena.services.ingestion import build_incident_envelope
from athena.services.submission import submit_ticket

router = APIRouter()
logger = logging.getLogger(__name__)


class AnalyzeRequest(BaseModel):
    job_id: int


@router.post("/api/v1/analyze")
async def analyze_job(body: AnalyzeRequest, request: Request):
    """Manually trigger analysis of a specific failed AAP2 job.

    Runs the full pipeline synchronously and returns the ticket info.
    """
    state = request.app.state._state

    envelope = await build_incident_envelope(state["aap2"], job_id=body.job_id)
    ticket_payload = await run_pipeline(envelope, state["settings"])
    result = await submit_ticket(
        payload=ticket_payload,
        kira=state["kira"],
        rocketchat=state["rocketchat"],
        kira_frontend_url=state["settings"].kira_url,
        rocketchat_channel=state["settings"].rocketchat_channel,
        job_name=envelope.job.name,
    )

    return {
        "status": "completed",
        "job_id": body.job_id,
        "job_name": envelope.job.name,
        "ticket_id": result["ticket_id"],
        "ticket_url": result["ticket_url"],
        "area": ticket_payload.area,
        "risk": ticket_payload.risk,
        "confidence": ticket_payload.confidence,
    }
```

- [ ] **Step 5: Create `athena/app.py`**

```python
"""FastAPI application with lifespan for client initialization and webhook registration."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from athena.adapters.aap2 import AAP2Client
from athena.adapters.kira import KiraClient
from athena.adapters.rocketchat import RocketChatClient
from athena.config import Settings
from athena.routes import analyze, health, webhook

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize clients and register AAP2 webhook on startup."""
    # Load and validate configuration
    settings = Settings()

    # Configure MaaS gateway for LangChain (OpenAI-compatible endpoint)
    os.environ["OPENAI_API_BASE"] = settings.litellm_api_base_url
    os.environ["OPENAI_API_KEY"] = settings.litellm_virtual_key.get_secret_value()

    # Optional: Tavily for web search
    if settings.tavily_api_key:
        os.environ["TAVILY_API_KEY"] = settings.tavily_api_key.get_secret_value()

    # Initialize adapter clients
    aap2 = AAP2Client(
        base_url=settings.aap2_url,
        username=settings.aap2_username,
        password=settings.aap2_password.get_secret_value(),
    )
    kira = KiraClient(
        base_url=settings.kira_url,
        api_key=settings.kira_api_key.get_secret_value(),
    )
    rocketchat = RocketChatClient(
        base_url=settings.rocketchat_url,
        auth_token=settings.rocketchat_api_auth_token.get_secret_value(),
        user_id=settings.rocketchat_api_user_id,
    )

    # Store in app state for route handlers
    app.state._state = {
        "settings": settings,
        "aap2": aap2,
        "kira": kira,
        "rocketchat": rocketchat,
    }

    # Register webhook in AAP2 (idempotent)
    try:
        webhook_url = settings.athena_base_url or "http://athena:8080"
        target = f"{webhook_url.rstrip('/')}{settings.athena_webhook_path}"
        template_id = await aap2.register_webhook(target)
        logger.info("AAP2 webhook registered (template_id=%s)", template_id)
        health.set_ready(True)
    except Exception:
        logger.exception("Failed to register AAP2 webhook — readiness probe will fail")

    yield


app = FastAPI(
    title="Athena AIOps",
    description="Agentic AIOps service for AAP2 failure analysis",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(analyze.router)
```

- [ ] **Step 6: Commit**

```bash
git add athena/routes/__init__.py athena/routes/health.py athena/routes/webhook.py athena/routes/analyze.py athena/app.py
git commit -m "feat: add FastAPI app with webhook, analyze, and health routes"
```

---

## Task 11: End-to-End Pipeline Test

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/e2e/__init__.py`
- Create: `tests/e2e/test_pipeline.py`

- [ ] **Step 1: Create `__init__.py` files**

Create empty `tests/__init__.py` and `tests/e2e/__init__.py`.

- [ ] **Step 2: Write e2e pipeline test**

Create `tests/e2e/test_pipeline.py`:

```python
"""End-to-end pipeline test with mocked LLM and external services.

Tests the full flow: webhook → ingestion → (mocked) agent → submission → Kira + Rocket.Chat.
This validates wiring without burning LLM tokens.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from athena.models import TicketPayload


@pytest.fixture
def mock_ticket_payload() -> TicketPayload:
    return TicketPayload(
        title="Deploy Web App failed: missing httpd package",
        description="The playbook task 'install httpd' failed because httpd is not in the repo.",
        area="application",
        confidence=85,
        risk="high",
        stage="production",
        recommended_action="Add httpd to the Satellite content view for the production repo.",
        affected_systems=["web-server-01"],
        skills=["linux", "ansible"],
        issues=[],
    )


@pytest.fixture
def mock_env(monkeypatch: pytest.MonkeyPatch):
    """Set all required env vars for Settings."""
    env = {
        "aap2_url": "https://aap2.test",
        "aap2_username": "admin",
        "aap2_password": "secret",
        "aap2_organization": "org-test",
        "kira_url": "https://kira.test",
        "kira_api_key": "key-123",
        "rocketchat_url": "https://chat.test",
        "rocketchat_api_auth_token": "token-abc",
        "rocketchat_api_user_id": "user-123",
        "litellm_api_base_url": "https://maas.test/v1",
        "litellm_virtual_key": "sk-test",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)


async def test_analyze_endpoint_full_pipeline(mock_env, mock_ticket_payload):
    """Test POST /api/v1/analyze runs the full pipeline with mocked internals."""
    mock_aap2 = AsyncMock()
    mock_aap2.get_job.return_value = {
        "id": 42,
        "name": "Deploy Web App",
        "status": "failed",
        "summary_fields": {
            "job_template": {"id": 10, "name": "deploy-web"},
            "project": {"name": "web-project"},
            "inventory": {"name": "production"},
            "execution_environment": {"name": "Default EE"},
        },
        "playbook": "playbooks/deploy.yml",
        "started": "2026-04-15T10:00:00+00:00",
        "finished": "2026-04-15T10:05:00+00:00",
    }
    mock_aap2.get_job_stdout.return_value = "TASK [install] fatal: FAILED\n"
    mock_aap2.get_job_events.return_value = [{"event": "runner_on_failed"}]
    mock_aap2.register_webhook.return_value = 1

    mock_kira = AsyncMock()
    mock_kira.create_ticket.return_value = {"id": "ticket-uuid-123", "title": "test"}
    mock_kira.create_issue.return_value = {"id": "issue-uuid-456"}

    mock_rocketchat = AsyncMock()
    mock_rocketchat.post_message.return_value = "msg-001"

    with (
        patch("athena.app.AAP2Client", return_value=mock_aap2),
        patch("athena.app.KiraClient", return_value=mock_kira),
        patch("athena.app.RocketChatClient", return_value=mock_rocketchat),
        patch(
            "athena.agents.pipeline.run_pipeline",
            return_value=mock_ticket_payload,
        ),
    ):
        from athena.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/analyze", json={"job_id": 42})

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticket_id"] == "ticket-uuid-123"
    assert data["area"] == "application"
    assert data["confidence"] == 85
```

- [ ] **Step 3: Run test**

```bash
uv run pytest tests/e2e/test_pipeline.py -v
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/__init__.py tests/e2e/__init__.py tests/e2e/test_pipeline.py
git commit -m "test: add end-to-end pipeline test with mocked LLM"
```

---

## Task 12: Dockerfile

**Files:**
- Create: `Dockerfile`

- [ ] **Step 1: Create `Dockerfile`**

```dockerfile
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY athena/ athena/
COPY AGENTS.md subagents.yaml ./
COPY skills/ skills/
COPY templates/ templates/

# Install the project itself
RUN uv sync --no-dev

FROM python:3.13-slim

# Non-root user for OpenShift compatibility
RUN useradd --create-home --uid 1001 athena
USER 1001
WORKDIR /app

# Copy installed venv and app from builder
COPY --from=builder --chown=1001:1001 /app /app

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

CMD ["uvicorn", "athena.app:app", "--host", "0.0.0.0", "--port", "8080"]
```

- [ ] **Step 2: Commit**

```bash
git add Dockerfile
git commit -m "feat: add multi-stage Dockerfile with non-root user"
```

---

## Task 13: Helm Chart

**Files:**
- Create: `deploy/helm/athena/Chart.yaml`
- Create: `deploy/helm/athena/values.yaml`
- Create: `deploy/helm/athena/templates/_helpers.tpl`
- Create: `deploy/helm/athena/templates/deployment.yaml`
- Create: `deploy/helm/athena/templates/service.yaml`
- Create: `deploy/helm/athena/templates/route.yaml`
- Create: `deploy/helm/athena/templates/secret.yaml`
- Create: `deploy/helm/athena/templates/configmap.yaml`
- Create: `deploy/helm/athena/templates/pvc.yaml`

- [ ] **Step 1: Create `deploy/helm/athena/Chart.yaml`**

```yaml
apiVersion: v2
name: athena
description: Athena AIOps — Agentic failure analysis for AAP2
type: application
version: 0.1.0
appVersion: "0.1.0"
```

- [ ] **Step 2: Create `deploy/helm/athena/values.yaml`**

```yaml
image:
  repository: quay.io/tonykay/athena-aiops
  tag: latest
  pullPolicy: Always

aap2:
  url: ""
  username: ""
  password: ""
  organization: ""

kira:
  url: ""
  apiKey: ""

rocketchat:
  url: ""
  apiAuthToken: ""
  apiUserId: ""
  channel: "support"

# MaaS (LLM gateway) — uses litellm_* env var names per provisioning system
maas:
  apiBaseUrl: ""
  virtualKey: ""

tavily:
  apiKey: ""

service:
  port: 8080
  type: ClusterIP

route:
  enabled: true

agentConfig:
  opsManagerModel: "openai/claude-sonnet-4-6"
  specialistModel: "openai/claude-sonnet-4-6"
  reviewerModel: "openai/claude-3-5-haiku"
  # Optional: override AGENTS.md and subagents.yaml baked into the image
  # Use --set-file agentConfig.agentsMd=./AGENTS.md to override
  agentsMd: ""
  subagentsYaml: ""

skills:
  persistence:
    enabled: true
    size: 1Gi

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

- [ ] **Step 3: Create `deploy/helm/athena/templates/_helpers.tpl`**

```yaml
{{- define "athena.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "athena.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "athena.labels" -}}
app.kubernetes.io/name: {{ include "athena.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "athena.selectorLabels" -}}
app.kubernetes.io/name: {{ include "athena.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
```

- [ ] **Step 4: Create `deploy/helm/athena/templates/secret.yaml`**

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: {{ include "athena.fullname" . }}
  labels:
    {{- include "athena.labels" . | nindent 4 }}
type: Opaque
stringData:
  aap2-password: {{ .Values.aap2.password | quote }}
  kira-api-key: {{ .Values.kira.apiKey | quote }}
  rocketchat-auth-token: {{ .Values.rocketchat.apiAuthToken | quote }}
  maas-virtual-key: {{ .Values.maas.virtualKey | quote }}
  {{- if .Values.tavily.apiKey }}
  tavily-api-key: {{ .Values.tavily.apiKey | quote }}
  {{- end }}
```

- [ ] **Step 5: Create `deploy/helm/athena/templates/configmap.yaml`**

Note: AGENTS.md and subagents.yaml are baked into the container image. This ConfigMap allows overriding them without rebuilding. The values default to empty — when empty, the container uses its baked-in copies. When set via `--set-file` or values override, the ConfigMap mount takes precedence.

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ include "athena.fullname" . }}-config
  labels:
    {{- include "athena.labels" . | nindent 4 }}
data:
  {{- if .Values.agentConfig.agentsMd }}
  AGENTS.md: |
    {{- .Values.agentConfig.agentsMd | nindent 4 }}
  {{- end }}
  {{- if .Values.agentConfig.subagentsYaml }}
  subagents.yaml: |
    {{- .Values.agentConfig.subagentsYaml | nindent 4 }}
  {{- end }}
```

- [ ] **Step 6: Create `deploy/helm/athena/templates/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: {{ include "athena.fullname" . }}
  labels:
    {{- include "athena.labels" . | nindent 4 }}
spec:
  replicas: 1
  selector:
    matchLabels:
      {{- include "athena.selectorLabels" . | nindent 6 }}
  template:
    metadata:
      labels:
        {{- include "athena.selectorLabels" . | nindent 8 }}
    spec:
      containers:
        - name: athena
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          ports:
            - containerPort: {{ .Values.service.port }}
              protocol: TCP
          env:
            # AAP2
            - name: AAP2_URL
              value: {{ .Values.aap2.url | quote }}
            - name: AAP2_USERNAME
              value: {{ .Values.aap2.username | quote }}
            - name: AAP2_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: {{ include "athena.fullname" . }}
                  key: aap2-password
            - name: AAP2_ORGANIZATION
              value: {{ .Values.aap2.organization | quote }}
            # Kira
            - name: KIRA_URL
              value: {{ .Values.kira.url | quote }}
            - name: KIRA_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "athena.fullname" . }}
                  key: kira-api-key
            # Rocket.Chat
            - name: ROCKETCHAT_URL
              value: {{ .Values.rocketchat.url | quote }}
            - name: ROCKETCHAT_API_AUTH_TOKEN
              valueFrom:
                secretKeyRef:
                  name: {{ include "athena.fullname" . }}
                  key: rocketchat-auth-token
            - name: ROCKETCHAT_API_USER_ID
              value: {{ .Values.rocketchat.apiUserId | quote }}
            - name: ROCKETCHAT_CHANNEL
              value: {{ .Values.rocketchat.channel | quote }}
            # MaaS (LLM gateway)
            - name: LITELLM_API_BASE_URL
              value: {{ .Values.maas.apiBaseUrl | quote }}
            - name: LITELLM_VIRTUAL_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "athena.fullname" . }}
                  key: maas-virtual-key
            {{- if .Values.tavily.apiKey }}
            - name: TAVILY_API_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "athena.fullname" . }}
                  key: tavily-api-key
            {{- end }}
          livenessProbe:
            httpGet:
              path: /healthz
              port: {{ .Values.service.port }}
            initialDelaySeconds: 10
            periodSeconds: 30
          readinessProbe:
            httpGet:
              path: /readyz
              port: {{ .Values.service.port }}
            initialDelaySeconds: 15
            periodSeconds: 10
          resources:
            {{- toYaml .Values.resources | nindent 12 }}
          volumeMounts:
            - name: config
              mountPath: /app/AGENTS.md
              subPath: AGENTS.md
            - name: config
              mountPath: /app/subagents.yaml
              subPath: subagents.yaml
            {{- if .Values.skills.persistence.enabled }}
            - name: skills
              mountPath: /app/skills
            {{- end }}
      volumes:
        - name: config
          configMap:
            name: {{ include "athena.fullname" . }}-config
        {{- if .Values.skills.persistence.enabled }}
        - name: skills
          persistentVolumeClaim:
            claimName: {{ include "athena.fullname" . }}-skills
        {{- end }}
```

- [ ] **Step 7: Create `deploy/helm/athena/templates/service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: {{ include "athena.fullname" . }}
  labels:
    {{- include "athena.labels" . | nindent 4 }}
spec:
  type: {{ .Values.service.type }}
  ports:
    - port: {{ .Values.service.port }}
      targetPort: {{ .Values.service.port }}
      protocol: TCP
      name: http
  selector:
    {{- include "athena.selectorLabels" . | nindent 4 }}
```

- [ ] **Step 8: Create `deploy/helm/athena/templates/route.yaml`**

```yaml
{{- if .Values.route.enabled }}
apiVersion: route.openshift.io/v1
kind: Route
metadata:
  name: {{ include "athena.fullname" . }}
  labels:
    {{- include "athena.labels" . | nindent 4 }}
spec:
  to:
    kind: Service
    name: {{ include "athena.fullname" . }}
    weight: 100
  port:
    targetPort: http
  tls:
    termination: edge
    insecureEdgeTerminationPolicy: Redirect
{{- end }}
```

- [ ] **Step 9: Create `deploy/helm/athena/templates/pvc.yaml`**

```yaml
{{- if .Values.skills.persistence.enabled }}
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: {{ include "athena.fullname" . }}-skills
  labels:
    {{- include "athena.labels" . | nindent 4 }}
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: {{ .Values.skills.persistence.size }}
{{- end }}
```

- [ ] **Step 10: Commit**

```bash
git add deploy/ Dockerfile
git commit -m "feat: add Helm chart for OpenShift deployment"
```

---

## Task 14: Run Full Test Suite and Lint

**Files:**
- No new files — validation of everything built in Tasks 1-13.

- [ ] **Step 1: Run linter**

```bash
uv run ruff check .
uv run ruff format --check .
```

Expected: No errors. If there are formatting issues, fix with `uv run ruff format .`.

- [ ] **Step 2: Run full test suite**

```bash
uv run pytest -v
```

Expected: All tests pass (test_config: 3, test_models: 8, test_kira: 3, test_rocketchat: 2, test_aap2: 5, test_ingestion: 2, test_submission: 3, test_pipeline e2e: 1 = **27 tests**).

- [ ] **Step 3: Fix any failures**

If any tests fail, fix the code and re-run until all pass.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore: lint fixes and full test suite passing"
```

---

## Task 15: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md to reflect the actual implementation**

Review `CLAUDE.md` and ensure it accurately reflects the implemented structure. Update the Commands section with any corrections, verify the architecture section matches what was built, and add any conventions discovered during implementation.

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md to reflect implemented architecture"
```
