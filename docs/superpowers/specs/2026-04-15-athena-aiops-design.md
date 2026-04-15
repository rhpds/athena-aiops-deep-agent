# Athena AIOps — Design Specification

**Date:** 2026-04-15
**Status:** Draft
**PRD:** `prd-athena.md`
**Approach:** Hybrid with Smart Reviewer (agents for classification, RCA, and review; deterministic code for API plumbing)

## Overview

Athena is an agentic AIOps service that listens for failed AAP2 Controller jobs, analyzes failures using a Deep Agents orchestration layer, and creates structured incident tickets in Kira via API. Notifications are posted to Rocket.Chat. Deployed as a single Python container on OpenShift via Helm chart.

This repo evolves from `../1st-pass-deepagents-poc/` which proved out the Deep Agents pattern with a simpler ops_manager + SRE subagent setup. Athena adds AAP2 webhook ingestion, ticket generation, the Kira adapter, a reviewer step, and OpenShift deployment.

## Architecture Decision: Hybrid with Smart Reviewer

The agentic pipeline handles what LLMs are good at — classification, root-cause analysis, and intelligent review. Deterministic Python code handles API plumbing — Kira submission, Rocket.Chat notification, schema validation.

- `ops_manager` classifies the failure domain and orchestrates delegation
- Specialist SRE subagents perform root-cause analysis using domain skills
- `reviewer` (on Haiku) validates coherence, confidence justification, and actionability
- `submission.py` takes the structured agent output and ships it to Kira and Rocket.Chat

The agent boundary falls exactly where LLM reasoning adds value.

## Project Structure

```
athena-aiops-deep-agent/
├── AGENTS.md                    # ops_manager persona & triage protocol
├── CLAUDE.md
├── prd-athena.md
├── pyproject.toml               # uv project, Python 3.13
├── subagents.yaml               # SRE specialists + reviewer config
│
├── athena/
│   ├── __init__.py
│   ├── __main__.py              # uvicorn entrypoint
│   ├── app.py                   # FastAPI app, lifespan (AAP2 webhook registration)
│   ├── config.py                # Pydantic Settings — all env vars
│   ├── models.py                # Pydantic V2 models
│   │
│   ├── routes/
│   │   ├── webhook.py           # POST /api/v1/webhook/aap2
│   │   ├── analyze.py           # POST /api/v1/analyze
│   │   └── health.py            # GET  /healthz, /readyz
│   │
│   ├── agents/
│   │   ├── pipeline.py          # Deep Agents wiring: create_ops_manager(), load_subagents()
│   │   └── tools.py             # @tool functions: aap2_*, web_search
│   │
│   ├── adapters/
│   │   ├── aap2.py              # AAP2 Controller API client
│   │   ├── kira.py              # Kira API client
│   │   └── rocketchat.py        # Rocket.Chat client
│   │
│   └── services/
│       ├── ingestion.py         # Normalize AAP2 data → IncidentEnvelope
│       └── submission.py        # Agent output → Kira + Rocket.Chat
│
├── skills/
│   ├── error-classifier/SKILL.md
│   ├── analyze-ansible-failure/SKILL.md
│   ├── analyze-linux-failure/SKILL.md
│   ├── analyze-openshift-failure/SKILL.md
│   ├── analyze-networking-failure/SKILL.md
│   ├── create-ticket/SKILL.md
│   ├── review-ticket/SKILL.md
│   └── common/
│       └── log-analysis/SKILL.md
│
├── templates/
│   └── ticket.md.j2             # Canonical TICKET.md template
│
├── deploy/
│   └── helm/
│       └── athena/
│           ├── Chart.yaml
│           ├── values.yaml
│           └── templates/
│
└── tests/
    ├── test_models.py
    ├── test_adapters/
    │   ├── test_aap2.py
    │   ├── test_kira.py
    │   └── test_rocketchat.py
    ├── test_services/
    │   ├── test_ingestion.py
    │   └── test_submission.py
    ├── integration/
    │   ├── test_aap2_integration.py
    │   ├── test_kira_integration.py
    │   └── test_rocketchat_integration.py
    └── e2e/
        └── test_pipeline.py
```

## Data Models

### IncidentEnvelope (incoming, normalized from AAP2)

```python
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
    playbook_path: str | None
    related_files: list[str]

class EnvironmentContext(BaseModel):
    cluster: str | None
    environment: Literal["dev", "test", "stage", "prod"] | None
    namespace: str | None

class IncidentEnvelope(BaseModel):
    event_id: str
    received_at: datetime
    source: Literal["aap2"]
    job: JobInfo
    artifacts: JobArtifacts
    context: EnvironmentContext
```

### TicketPayload (agent output, submitted to Kira)

```python
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
    affected_systems: list[str]
    skills: list[str]
    issues: list[IssuePayload]
```

Enum values and field mappings are validated against the Kira OpenAPI spec:
https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml

### Area Mapping

The agent pipeline uses internal domain names. `services/submission.py` maps these to Kira area values before API submission. The `TicketPayload` model uses Kira's enum values since it represents the final output.

| Agent Domain (error-classifier output) | Kira Area (TicketPayload.area) |
|-----------------------------------------|-------------------------------|
| `ansible` | `application` |
| `linux` | `linux` |
| `openshift` | `kubernetes` |
| `networking` | `networking` |

## Agent Pipeline

### Agent Hierarchy

```
AAP2 webhook → athena service → ops_manager (main agent)
                                    ├── sre_ansible     (playbook/role/collection/credential)
                                    ├── sre_linux       (dnf/systemd/SELinux/filesystem)
                                    ├── sre_openshift   (pod/image/RBAC/operator/networking)
                                    └── sre_networking  (DNS/SSH/proxy/TLS/routing)

ops_manager → reviewer (validates ticket quality)
           → returns TicketPayload (structured output)

submission.py → Kira API (create ticket + issues + artifacts)
             → Rocket.Chat #support (notification)
```

### End-to-End Flow

1. **Trigger**: AAP2 webhook `POST /api/v1/webhook/aap2` or manual `POST /api/v1/analyze {job_id}`
2. **Ingestion** (`services/ingestion.py`):
   - If webhook: parse notification payload, extract job ID
   - If manual: receive job ID directly
   - Call AAP2 adapter: `get_job()`, `get_job_stdout()`, `get_job_events()`, `get_job_template()`, `get_related_artifacts()`
   - Build and validate `IncidentEnvelope`
3. **Agent Pipeline** (`agents/pipeline.py`):
   - Write `IncidentEnvelope` as `incident.json` to `FilesystemBackend`
   - Invoke `ops_manager` with incident summary
   - `ops_manager` uses `error-classifier` skill → emits domain, confidence, rationale
   - `ops_manager` delegates via `task` tool to the matching specialist subagent
   - Specialist reads incident context, optionally calls `web_search`, uses domain analysis skill and `create-ticket` skill
   - `ops_manager` delegates to `reviewer` (Haiku) which uses `review-ticket` skill
   - `ops_manager` returns final `TicketPayload` as structured output
4. **Submission** (`services/submission.py`):
   - Validate `TicketPayload` against Kira enums
   - Map area (ansible→application, openshift→kubernetes)
   - `POST` ticket to Kira → get `ticket_id` + URL
   - For each issue: `POST` to Kira `/tickets/{id}/issues`
   - Upload `TICKET.md` as artifact to Kira
   - `POST` notification to Rocket.Chat `#support`

### ops_manager Configuration

`AGENTS.md` is loaded as persistent memory defining the ops_manager persona:

- **Role**: Receive normalized AAP2 job failure incidents, classify the failure domain, delegate to the right specialist, ensure the final output is a structured ticket
- **Triage protocol**: 1) Read the incident envelope, 2) Invoke error-classifier skill, 3) Delegate to one specialist via `task`, 4) Send specialist output to reviewer, 5) Return final TicketPayload as structured output
- **Escalation rule**: If error-classifier confidence < 50%, or reviewer flags the analysis as incoherent, set risk to "high" and add a note that manual review is needed
- **Output contract**: Always return a valid TicketPayload JSON

### Subagent Configuration (`subagents.yaml`)

| Subagent | Model | Kira Area | Skills | Tools |
|----------|-------|-----------|--------|-------|
| `sre_ansible` | `openai/claude-sonnet-4-6` | `application` | analyze-ansible-failure, create-ticket, common | web_search |
| `sre_linux` | `openai/claude-sonnet-4-6` | `linux` | analyze-linux-failure, create-ticket, common | web_search |
| `sre_openshift` | `openai/claude-sonnet-4-6` | `kubernetes` | analyze-openshift-failure, create-ticket, common | web_search |
| `sre_networking` | `openai/claude-sonnet-4-6` | `networking` | analyze-networking-failure, create-ticket, common | web_search |
| `reviewer` | `openai/claude-3-5-haiku` | — | review-ticket | — |

Models are prefixed `openai/` to route through the MaaS gateway (OpenAI-compatible endpoint). The MaaS base URL and API key are set via environment variables (`litellm_api_base_url`, `litellm_virtual_key`) and configured on the LangChain model at agent creation time.

## Skills

Each skill is a `SKILL.md` file in a directory under `skills/`. Loaded on-demand via `SkillsMiddleware`.

### error-classifier

Classifies the failure domain from the incident envelope.

1. Read the error excerpt and stdout
2. Identify domain signals:
   - Ansible keywords (task, role, collection, module, playbook, variable) → `ansible`
   - Linux keywords (dnf, yum, systemd, SELinux, permission denied, filesystem) → `linux`
   - OpenShift/K8s keywords (pod, container, image, RBAC, namespace, operator) → `openshift`
   - Network keywords (DNS, unreachable, timeout, connection refused, SSL, proxy, SSH) → `networking`
3. If signals span multiple domains, choose the root cause domain
4. Emit: domain, confidence (0-100), rationale

### analyze-ansible-failure

1. Read full incident context (stdout, events, template, playbook path)
2. Identify the failing task and specific error
3. Classify sub-category (syntax, collection missing, credential, EE, variable, template param)
4. Determine root cause with evidence
5. Assess risk and confidence
6. Produce specific recommended actions
7. List affected systems

### analyze-linux-failure

Same structure, focused on: package manager errors (repo access, dependency conflicts, Satellite), service failures (systemd unit status, dependencies), permission/SELinux issues (context mismatches, booleans), filesystem issues (space, mounts, ownership).

### analyze-openshift-failure

Same structure, focused on: pod lifecycle failures (CrashLoopBackOff, ImagePullBackOff, pending), RBAC and service account issues, resource limits and quota exhaustion, operator and CRD issues, route/service/ingress problems.

### analyze-networking-failure

Same structure, focused on: DNS resolution failures, SSH connectivity (timeout, key rejection, port blocked), proxy and TLS certificate errors, routing and firewall issues, host unreachable patterns.

### create-ticket

Guides the specialist on output structure:

1. Clear, concise title (what failed and why, < 100 chars)
2. Description with: summary, evidence from logs, root cause analysis, impact
3. Confidence (0-100) justified by evidence strength
4. Risk based on impact: critical (production down), high (degraded), medium (non-prod or limited), low (cosmetic)
5. Specific recommended actions (commands, config changes, file edits)
6. Affected systems by name
7. Sub-issues for each distinct problem found

### review-ticket

Validation checklist:

1. Title is specific (not generic like "Job failed")
2. Description contains evidence, not just assertions
3. Confidence score is justified — high confidence requires clear log evidence
4. Risk level matches actual impact described
5. Recommended actions are specific and actionable
6. No contradictions between root cause and recommendations
7. Return: `approved` with optional amendments, or `escalate` with reason

### common/log-analysis

Shared skill for parsing Ansible/AAP2 job output:

1. Identify task boundary markers in stdout
2. Extract failing task name, role, and play
3. Isolate error message from surrounding output
4. Note preceding warnings that may provide context
5. Identify stack traces or module-specific error codes

## Adapters

### AAP2 Adapter (`athena/adapters/aap2.py`)

Async `httpx` client. Basic auth (`aap2_username`/`aap2_password`).

```
AAP2Client:
  get_job(job_id) → job metadata
  get_job_stdout(job_id) → raw stdout text
  get_job_events(job_id) → failed events list
  get_job_template(template_id) → template details
  get_related_artifacts(job_id) → playbook path, project info, inventory
  register_webhook(target_url) → ensure notification template exists for job failures
```

`register_webhook()` runs during FastAPI lifespan startup:
1. List existing notification templates
2. If one already points at Athena's URL, done
3. Otherwise create a notification template (type: webhook, HTTP POST) for `job` events with status `failed`
4. Associate with a notification notifier targeting Athena's webhook URL

### Kira Adapter (`athena/adapters/kira.py`)

Async `httpx` client. Auth via `X-API-Key` header. Fields validated against https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml

```
KiraClient:
  create_ticket(payload: TicketPayload) → ticket_id, ticket_url
  create_issue(ticket_id, issue: IssuePayload) → issue_id
  upload_artifact(ticket_id, filename, content) → artifact_id
```

### Rocket.Chat Adapter (`athena/adapters/rocketchat.py`)

Async `httpx` client. Auth via `X-Auth-Token` + `X-User-Id` headers.

```
RocketChatClient:
  post_message(channel, text) → message_id
```

### Notification Format (Rocket.Chat #support)

```
<risk-emoji> <job-name> failed — <area> | <risk> | confidence: <N>% | <stage>
  <one-line recommended action>
  <kira-ticket-link>
```

The Kira link should open in the Kira frontend iframe when possible.

## API Endpoints

### POST /api/v1/webhook/aap2

AAP2 notification webhook receiver. Receives the AAP2 notification payload, extracts the job ID, kicks off the pipeline as a background task. Returns `202 Accepted` immediately.

### POST /api/v1/analyze

Manual trigger. Request body: `{ "job_id": "123" }`. Runs the full pipeline synchronously and returns the created ticket info (ticket ID, URL, summary). Used during workshops to analyze a specific failed job on demand.

### GET /healthz

Liveness probe. Returns 200 if the service process is running.

### GET /readyz

Readiness probe. Returns 200 if AAP2 connection is verified and webhook is registered.

### GET /docs

Auto-generated OpenAPI documentation (built into FastAPI).

## Configuration

### Environment Variables

```python
class Settings(BaseSettings):
    # AAP2 Controller
    aap2_url: str
    aap2_username: str
    aap2_password: SecretStr
    aap2_organization: str

    # Kira
    kira_url: str
    kira_api_key: SecretStr

    # Rocket.Chat
    rocketchat_url: str
    rocketchat_api_auth_token: SecretStr
    rocketchat_api_user_id: str
    rocketchat_channel: str = "support"

    # MaaS (LLM gateway) — env vars are litellm_* per provisioning system
    litellm_api_base_url: str
    litellm_virtual_key: SecretStr

    # Optional
    tavily_api_key: SecretStr | None = None

    # Athena
    athena_webhook_path: str = "/api/v1/webhook/aap2"
    athena_base_url: str | None = None  # Auto-detected from OpenShift route if not set
```

### Runtime Files (ConfigMap-mounted)

- `AGENTS.md` — ops_manager persona and triage protocol
- `subagents.yaml` — subagent definitions (editable without rebuild)

### Skills (PVC-mounted)

- `skills/` directory — add or modify skills without rebuilding the container

## Helm Chart

### `deploy/helm/athena/values.yaml`

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

skills:
  persistence:
    enabled: true
    size: 1Gi
```

### Templates

- `deployment.yaml` — single pod, env vars from Secret, ConfigMap mounts for AGENTS.md + subagents.yaml, PVC mount for skills/
- `service.yaml` — ClusterIP on port 8080
- `route.yaml` — OpenShift Route (AAP2 posts webhooks here)
- `secret.yaml` — all credentials
- `configmap.yaml` — AGENTS.md and subagents.yaml content
- `pvc.yaml` — skills volume

### Startup Sequence

1. Pod starts
2. FastAPI lifespan begins
3. Load Settings from env vars (fail fast if required vars missing)
4. Initialize AAP2Client, KiraClient, RocketChatClient
5. Readiness probe: verify AAP2 connectivity
6. Register webhook in AAP2 (idempotent)
7. Begin accepting requests

### Container

- Base image: `python:3.13-slim`
- Install via `uv` in Dockerfile
- Run: `uvicorn athena.app:app --host 0.0.0.0 --port 8080`
- Non-root user, read-only filesystem (except skills PVC mount)

## Testing Strategy

### Unit Tests

- `tests/test_models.py` — Pydantic model validation, enum constraints, area mapping
- `tests/test_adapters/test_aap2.py` — URL construction, auth, response parsing, idempotent webhook registration
- `tests/test_adapters/test_kira.py` — correct headers (`X-API-Key`), TicketPayload→Kira schema mapping per OpenAPI spec, error handling
- `tests/test_adapters/test_rocketchat.py` — message formatting, auth headers
- `tests/test_services/test_ingestion.py` — raw AAP2 webhook → valid IncidentEnvelope
- `tests/test_services/test_submission.py` — TicketPayload → Kira + Rocket.Chat, partial failure handling

### Integration Tests (opt-in, skipped without env vars)

- `tests/integration/test_aap2_integration.py` — fetch real job from AAP2, verify parsing
- `tests/integration/test_kira_integration.py` — create/retrieve real ticket, verify against OpenAPI spec
- `tests/integration/test_rocketchat_integration.py` — post test message to #support

### End-to-End Test

- `tests/e2e/test_pipeline.py` — full pipeline with mocked LLM responses: webhook → ingestion → agent input → mock structured output → Kira ticket → Rocket.Chat notification

### Out of Scope for Testing

- LLM reasoning quality (skills and reviewer handle this)
- Deep Agents framework internals
- Kira/Rocket.Chat internal behavior

## Resources and References

- [LangChain Deep Agents repo](https://github.com/langchain-ai/deepagents.git) — framework source and `examples/` directory
- [Kira ticketing system](https://github.com/tonykay/kira) — source and deployment
- [Kira OpenAPI spec](https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml) — authoritative field/enum reference
- [Introducing Deep Agents](https://blog.langchain.com/deep-agents/)
- [Doubling Down on Deep Agents](https://blog.langchain.com/doubling-down-on-deepagents/)
- [Using Skills with Deep Agents](https://blog.langchain.com/using-skills-with-deep-agents/)
- [Building Multi-Agent Applications with Deep Agents](https://blog.langchain.com/building-multi-agent-applications-with-deep-agents/)
