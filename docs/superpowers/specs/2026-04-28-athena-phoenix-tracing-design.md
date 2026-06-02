# Athena Phoenix Tracing Design

**Date:** 2026-04-28
**Status:** Approved

## Goal

Add end-to-end observability to the Athena AIOps pipeline using Phoenix (Arize) as the tracing backend. Students and operators can browse traces in the Phoenix UI to see:

- `ops_manager` reasoning and ReAct cycle (alternating LLM → tool → LLM spans)
- Every tool call with inputs and outputs
- Full message context (exactly what each model received)
- SRE subagent delegation, execution, and tool use
- End-to-end flow from AAP2 webhook receipt to Kira ticket submission

## Framework Choice

**Phoenix (Arize)** — Apache 2.0, fully FOSS, purpose-built for LLM/agent observability.

- `openinference-instrumentation-langchain` auto-instruments all LangGraph nodes, LLM calls, and tool calls via LangChain callbacks — zero agent code changes
- Phoenix server provides the OTEL collector and web UI in a single pod
- Ephemeral in-memory storage (PVC-backed persistence tracked separately in `athena-aiops-deep-agent-wda`)

## Architecture

```
AAP2 webhook
    │
    ▼
[Athena pod]  ──OTEL gRPC (port 4317)──▶  [Phoenix pod]
    │                                           │
    │  auto-instrumented LangChain callbacks    ▼
    │  + manual spans (ingestion/submission)  Phoenix UI (port 6006)
    │                                           ◀── browser / OpenShift Route
    ▼
Kira / Rocket.Chat
```

Phoenix runs as a standalone pod in the same namespace as Athena. Tracing is opt-in: if `PHOENIX_COLLECTOR_ENDPOINT` is unset, instrumentation is skipped entirely — no-op in environments without Phoenix deployed.

## Span Hierarchy

```
POST /api/v1/webhook/aap2              ← manual root span
├── ingest_incident                    ← manual: AAP2 artifact fetch → IncidentEnvelope
└── run_pipeline                       ← manual: full agent execution
    ├── ops_manager: LLM call          ← auto: system prompt + incident summary visible
    ├── ops_manager: read_file         ← auto: tool call, path + content
    ├── ops_manager: task→sre_<domain> ← auto: subagent delegation
    │   ├── sre_<domain>: LLM call     ← auto: full SRE context + skill content
    │   ├── sre_<domain>: read_file    ← auto: incident.json
    │   └── sre_<domain>: web_search   ← auto: query + result snippet
    ├── ops_manager: task→reviewer     ← auto: reviewer delegation
    │   └── reviewer: LLM call         ← auto: ticket + review verdict
    └── ops_manager: LLM call          ← auto: final TicketPayload output
└── submit_ticket                      ← manual: Kira POST + Rocket.Chat notify
```

Each LLM span exposes: full input message list, output, token counts, latency. The ReAct cycle is visible as the alternating LLM → tool → LLM waterfall within `run_pipeline`.

## Code Changes

### 1. `pyproject.toml` — new dependencies

```toml
"openinference-instrumentation-langchain>=0.1",
"arize-phoenix-otel>=0.1",
"opentelemetry-exporter-otlp-proto-grpc>=1.0",
```

### 2. `athena/config.py` — new optional setting

```python
phoenix_collector_endpoint: str | None = None
# e.g. "http://phoenix:4317" (OpenShift) or "http://localhost:4317" (local dev)
```

### 3. `athena/app.py` — instrumentation setup in lifespan

At the top of the `lifespan` context manager, before the FastAPI app starts serving:

```python
if settings.phoenix_collector_endpoint:
    from phoenix.otel import register
    from openinference.instrumentation.langchain import LangChainInstrumentor

    register(endpoint=settings.phoenix_collector_endpoint)
    LangChainInstrumentor().instrument()
```

This is the only required instrumentation call. All LangGraph/LangChain activity is captured automatically from this point.

### 4. Manual spans — three files

**`athena/routes/webhook.py`** (and `routes/analyze.py`):

```python
from opentelemetry import trace
tracer = trace.get_tracer("athena")

# wrap the handler body:
with tracer.start_as_current_span("POST /api/v1/webhook/aap2") as span:
    span.set_attribute("aap2.job_id", payload.job_id)
    ...
```

**`athena/services/ingestion.py`**:

```python
with tracer.start_as_current_span("ingest_incident") as span:
    span.set_attribute("incident.event_id", event_id)
    # existing AAP2 artifact fetch logic
```

**`athena/services/submission.py`**:

```python
with tracer.start_as_current_span("submit_ticket") as span:
    span.set_attribute("kira.ticket_id", ticket_id)
    # existing Kira + Rocket.Chat calls
```

The tracer should be a module-level singleton: `tracer = trace.get_tracer("athena")`. If Phoenix is not configured the OTEL API is a no-op — no import guards needed.

## Deployment

### Phoenix pod (new Helm templates in `deploy/helm/athena/`)

- `templates/phoenix-deployment.yaml` — single container, `ghcr.io/arize-ai/phoenix:latest`, resources `requests: 256Mi/100m limits: 512Mi/500m`
- `templates/phoenix-service.yaml` — ClusterIP, ports 6006 (UI) and 4317 (OTEL gRPC)
- `templates/phoenix-route.yaml` — OpenShift Route exposing port 6006 for browser access
- Controlled by `values.yaml` key `phoenix.enabled: true`

### Athena Deployment env var (existing `templates/deployment.yaml`)

```yaml
- name: PHOENIX_COLLECTOR_ENDPOINT
  value: "http://phoenix:4317"
```

Only injected when `phoenix.enabled: true`.

### Local development

```bash
podman run -p 6006:6006 -p 4317:4317 ghcr.io/arize-ai/phoenix
export PHOENIX_COLLECTOR_ENDPOINT=http://localhost:4317
uv run python -m athena
# browse traces at http://localhost:6006
```

## Out of Scope

- Persistent trace storage (tracked in `athena-aiops-deep-agent-wda`)
- Showroom lab module for Phoenix (tracked in `athena-aiops-deep-agent-dhd`)
- Display of trace summary in Kira ticket view (tracked in `athena-aiops-deep-agent-oqz`)
- Existing Langfuse beads (`athena-aiops-deep-agent-98q`, `athena-aiops-deep-agent-2vi`) should be closed — superseded by this design
