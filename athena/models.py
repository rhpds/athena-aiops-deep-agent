"""Pydantic V2 data models for Athena AIOps.

Enum values for TicketPayload fields match the Kira OpenAPI spec:
https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

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


_STAGE_ALIASES: dict[str, str] = {
    "development": "dev",
    "develop": "dev",
    "testing": "test",
    "staging": "test",
    "stage": "test",
    "prod": "production",
}


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

    @field_validator("stage", mode="before")
    @classmethod
    def normalize_stage(cls, v: str) -> str:
        return _STAGE_ALIASES.get(v.lower(), v.lower()) if isinstance(v, str) else v
