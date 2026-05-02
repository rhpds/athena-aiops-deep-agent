# LangFuse Tracing for Athena

Add LangFuse observability to Athena so lab students can explore agent traces — seeing the full lifecycle from classification through SRE delegation to ticket creation.

## Problem

Students interact with Athena through its outputs (Kira tickets, Rocket.Chat notifications) but can't see what happens inside the agent pipeline. They can't observe how ops_manager classifies failures, how specialist SREs "come to life," which skills guide reasoning, or how the reviewer validates quality. LangFuse traces make all of this visible.

## Decisions

- **Backend**: LangFuse (replacing the earlier Phoenix design)
- **Integration**: LangChain `CallbackHandler` — auto-instruments all LLM calls, tool invocations, and subagent delegation with zero changes to `pipeline.py`
- **Opt-in**: Tracing activates only when `LANGFUSE_SECRET_KEY` is set. If unset, Athena behaves identically to today.
- **Deployment**: LangFuse runs per-tenant with its own PostgreSQL pod (isolated from Kira)
- **Lab style**: Pre-wired. Students trigger a failed job and explore traces in the LangFuse UI — no configuration required.
- **Showroom branch**: Lab module changes go to the `tok-01` branch

## Scope

### In scope

1. Athena code: add LangFuse callback handler (~20 lines across 3 files)
2. LangFuse deployment: Helm chart + deployer role for per-tenant LangFuse
3. Athena deployer: wire LangFuse env vars into Athena deployment
4. Showroom lab module: "Observing the Agent Pipeline" content

### Out of scope

- Manual spans for webhook/ingestion/submission (Approach B — not needed)
- OTEL instrumentation (Approach C — overkill)
- LangFuse user management (single shared project per tenant is sufficient)
- Cost tracking dashboards (students can see token counts in traces)

## Athena Code Changes

### 1. `pyproject.toml` — add dependency

```toml
"langfuse>=2.0",
```

### 2. `athena/config.py` — add optional settings

```python
langfuse_secret_key: SecretStr | None = None
langfuse_public_key: str | None = None
langfuse_host: str | None = None
```

All default to `None`. When unset, no tracing behavior — Athena is identical to today.

### 3. `athena/app.py` — register callback in lifespan

In the existing `lifespan()` async context manager, add after client initialization:

```python
if settings.langfuse_secret_key:
    from langfuse.callback import CallbackHandler
    langfuse_handler = CallbackHandler(
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        public_key=settings.langfuse_public_key,
        host=settings.langfuse_host,
    )
    import langchain_core
    langchain_core.callbacks.manager.set_handler(langfuse_handler)
    logger.info("LangFuse tracing enabled → %s", settings.langfuse_host)
```

This registers LangFuse as a global callback for all LangChain operations. Every `agent.astream()` call in `pipeline.py` automatically reports traces — no pipeline code changes.

### Risk mitigation

- If LangFuse is unreachable, the callback handler logs a warning but does not crash. The pipeline continues processing normally.
- If the env vars are unset, the `if` block never executes. Zero behavioral change.
- `pipeline.py` is completely untouched — the callback hooks into LangChain's global callback system externally.

## What Gets Traced Automatically

The LangChain callback handler auto-captures:

```
▼ ops_manager (GENERATION)
  ├─ LLM  claude-sonnet-4-6 — classify domain
  ├─ TOOL read_file — skills/error-classifier/SKILL.md
  ├─ TOOL read_file — incident.json
  ├─ TOOL task — delegate to sre_linux
  │   ▼ sre_linux (GENERATION)
  │     ├─ TOOL read_file — skills/analyze-linux-failure/SKILL.md
  │     ├─ TOOL read_file — incident.json
  │     ├─ LLM  claude-sonnet-4-6 — root cause analysis
  │     └─ LLM  claude-sonnet-4-6 — format analysis
  ├─ TOOL task — delegate to reviewer
  │   ▼ reviewer (GENERATION)
  │     └─ LLM  claude-3-5-haiku — validate ticket quality
  └─ LLM  claude-sonnet-4-6 — final TicketPayload
```

Students can see:
- **Classification**: ops_manager reading the error-classifier skill and determining domain/confidence/delegate_to
- **SRE lifecycle**: sre_linux loading its domain skill, reading incident context, performing multi-step RCA
- **Skill selection**: `read_file` calls to `skills/*/SKILL.md` visible as tool invocations
- **Model routing**: Sonnet for analysis, Haiku for review
- **Token usage and latency**: per-call metrics in the LangFuse UI

## LangFuse Deployment

### Architecture

Per-tenant deployment in the `{user}-agentic` namespace:

- **LangFuse container**: Single `langfuse/langfuse` image
- **PostgreSQL**: Dedicated `langfuse-postgres` pod (isolated from Kira's database)
- **Route**: OpenShift Route exposing the LangFuse web UI
- **Pre-configured**: A default project and API keys generated at deploy time

### Helm chart

Create `deploy/helm/langfuse/` with:
- `langfuse` Deployment (single container)
- `langfuse-postgres` Deployment + PVC
- Service + Route for UI access
- ConfigMap with project defaults
- Secret with generated API keys

### Deployer role

Add `ocp4_workload_langfuse_tenant` to `deepagents-aiops`:
- Deploy LangFuse Helm chart per tenant
- Generate API key pair
- Pass keys to Athena's deployment as env vars (`LANGFUSE_SECRET_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_HOST`)

### Athena deployer update

Modify `ocp4_workload_athena_tenant` to:
- Accept optional LangFuse env vars
- Wire them into the Athena Helm chart values
- LangFuse host points to the in-cluster service: `http://langfuse.{namespace}.svc.cluster.local:3000`

## Lab Module: Observing the Agent Pipeline

New showroom module on the `tok-01` branch. Content flow:

### 1. Introduction

Context-setting: "You've seen Athena analyze failures and create tickets. But what's happening inside the agent pipeline? In this module, you'll use LangFuse to see exactly how ops_manager classifies incidents, delegates to specialist SREs, and produces structured tickets."

### 2. Open LangFuse

Navigate to the LangFuse UI (link provided in showroom). Log in with pre-configured credentials.

### 3. Trigger a failed job

Launch the "Install Python 3.14" job template in AAP2 (same pattern as earlier modules). Wait for Athena to process it and create a Kira ticket.

### 4. Explore the trace

Walk through the trace hierarchy:
- Find the trace in the LangFuse traces list
- Identify ops_manager's classification step (domain, confidence, delegate_to)
- Watch sre_linux "come to life" — see it load its analysis skill, read incident context, perform root cause analysis
- See the reviewer validating ticket quality on Haiku (cheaper model)
- See the final TicketPayload JSON output

### 5. Key observations

Prompt students to notice:
- **Token usage**: how many tokens each agent consumes
- **Latency breakdown**: which step takes longest (usually the specialist RCA)
- **Model selection**: Sonnet for reasoning, Haiku for validation — cost optimization
- **Skill-driven behavior**: SKILL.md reads guide the agent's approach (visible as tool calls)
- **Structured output**: the final JSON payload that becomes a Kira ticket

## Files Changed

### Athena (`athena-aiops-deep-agent`)

| File | Change |
|------|--------|
| `pyproject.toml` | Add `langfuse>=2.0` |
| `athena/config.py` | Add 3 optional LangFuse env vars |
| `athena/app.py` | Register callback handler in lifespan (guarded by env var) |

### Athena Helm chart (`deploy/helm/athena/`)

| File | Change |
|------|--------|
| `values.yaml` | Add optional `langfuse.*` values |
| `templates/deployment.yaml` | Wire LangFuse env vars into container |
| `templates/secret.yaml` | Include LangFuse secret key |

### LangFuse Helm chart (new: `deploy/helm/langfuse/`)

| File | Change |
|------|--------|
| `Chart.yaml` | Chart metadata |
| `values.yaml` | Default config |
| `templates/deployment.yaml` | LangFuse container |
| `templates/postgres.yaml` | PostgreSQL for LangFuse |
| `templates/service.yaml` | ClusterIP service |
| `templates/route.yaml` | OpenShift Route |
| `templates/secret.yaml` | Generated API keys |

### Deployer (`deepagents-aiops`)

| File | Change |
|------|--------|
| `roles/ocp4_workload_langfuse_tenant/` | New role: deploy LangFuse per tenant |
| `roles/ocp4_workload_athena_tenant/defaults/main.yml` | Add LangFuse env var defaults |
| `roles/ocp4_workload_athena_tenant/tasks/workload.yml` | Wire LangFuse vars to Athena |

### Showroom (`showroom-summit-2026-lb2465-agentic-ai-ops`, branch `tok-01`)

| File | Change |
|------|--------|
| `content/modules/ROOT/pages/09-module-07-tracing.adoc` | New lab module |
| `content/modules/ROOT/pages/09-conclusion.adoc` → `10-conclusion.adoc` | Renumber conclusion |
| `content/modules/ROOT/pages/10-bonus-deep-agents-deep-dive.adoc` → `11-bonus-deep-agents-deep-dive.adoc` | Renumber bonus |
| `content/modules/ROOT/nav.adoc` | Add module to navigation |

## Testing

- Deploy LangFuse and Athena with tracing enabled to a test namespace
- Trigger "Install Python 3.14" failed job
- Verify trace appears in LangFuse UI with the expected hierarchy
- Verify Athena still creates the Kira ticket and Rocket.Chat notification normally
- Verify Athena works normally when LangFuse env vars are unset (no tracing, no errors)
- Verify Athena continues working when LangFuse is unreachable (graceful degradation)

## Supersedes

This design replaces `docs/superpowers/specs/2026-04-28-athena-phoenix-tracing-design.md`. The Phoenix design was approved but never implemented. LangFuse is the tracing backend going forward.
