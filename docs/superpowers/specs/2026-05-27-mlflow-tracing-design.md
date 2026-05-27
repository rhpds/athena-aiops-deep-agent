# MLflow Tracing for Athena (Dual-Backend)

Add MLflow observability alongside the existing LangFuse integration so both tracing backends fire on every pipeline run. This enables side-by-side comparison as the project evaluates MLflow as the strategic tracing platform.

## Problem

LangFuse is the current tracing backend for Athena. The strategic direction is MLflow. Rather than a risky swap, we want to run both in parallel on development clusters so we can compare trace quality, UI experience, and integration ergonomics before committing to a migration.

## Decisions

- **Backend**: MLflow added alongside LangFuse (not replacing it)
- **Integration**: `mlflow.langchain.autolog()` — global LangChain callback that captures all LLM calls, tool invocations, and subagent delegation automatically
- **Opt-in**: MLflow tracing activates only when `MLFLOW_TRACKING_URI` is set. If unset, Athena behaves identically to today.
- **Deployment**: Shared cluster-wide MLflow tracking server (not per-tenant). Tenants isolated by MLflow experiment name.
- **Scope**: Dev clusters only. Production (event.yaml) unchanged. No lab module content.
- **Coexistence**: Both LangFuse CallbackHandler (per-run) and MLflow autolog (global) fire simultaneously on every `agent.astream()` call.

## Scope

### In scope

1. Athena code: add MLflow autolog alongside LangFuse (~15 lines across 3 files)
2. Athena Helm chart: add optional MLflow env vars (same pattern as LangFuse)
3. Cluster workload: new `ocp4_workload_mlflow_cluster` role in `rhpds.deepagents_aiops` — deploys shared MLflow tracking server via Helm
4. Tenant workload: new `ocp4_workload_mlflow_tenant` role — creates per-tenant MLflow experiment, wires env vars to Athena
5. Showroom: add MLflow console tab (dev only)
6. agnosticv: wire workloads into `dev.yaml` (not `event.yaml`)

### Out of scope

- Removing LangFuse (future work — after comparison period)
- Lab module content for MLflow (future work)
- MLflow authentication (dev environment only)
- MLflow model registry features (we only use experiment tracking / GenAI tracing)
- RHOAI-managed MLflow (using standalone Helm deployment instead)
- Event/production deployment

## Subsystem Decomposition

```
1. Cluster Workload (deepagents-aiops + agnosticv)
   └─ Deploys shared MLflow tracking server cluster-wide
   
2. Tenant Workload (deepagents-aiops + agnosticv)
   └─ Creates per-tenant MLflow experiment + configures Athena env vars
   └─ Depends on: (1)

3. Athena Tracing (athena-aiops-deep-agent)
   └─ Adds mlflow.langchain.autolog() alongside LangFuse CallbackHandler
   └─ Independent code change; runtime depends on (1, 2)

4. Showroom Tab (agnosticv)
   └─ Adds MLflow console tab to showroom UI config
   └─ Depends on: (1)
```

## Athena Code Changes

### 1. `pyproject.toml` — add dependency

```toml
"mlflow>=2.15",
```

### 2. `athena/config.py` — add optional settings

```python
# MLflow tracing (opt-in — if unset, no tracing)
mlflow_tracking_uri: str | None = None
mlflow_experiment_name: str | None = None
```

Both default to `None`. When unset, no MLflow behavior — identical to today.

### 3. `athena/app.py` — register autolog in lifespan

In the existing `lifespan()` async context manager, add after the LangFuse initialization block:

```python
if settings.mlflow_tracking_uri:
    import mlflow
    mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
    mlflow.set_experiment(settings.mlflow_experiment_name or "athena-default")
    mlflow.langchain.autolog()
    logger.info("MLflow tracing enabled → %s", settings.mlflow_tracking_uri)
```

### How dual tracing works

LangFuse and MLflow hook into LangChain's callback system differently:

- **LangFuse**: Per-run `CallbackHandler()` instance injected into `astream_config["callbacks"]` in `pipeline.py`. Explicit per-invocation.
- **MLflow**: Global `autolog()` monkey-patches LangChain internals. Fires automatically on every LLM/tool/chain call after `autolog()` is called once.

Both coexist because they use independent callback mechanisms. LangFuse is a registered callback handler; MLflow patches the underlying call sites. No conflicts, no ordering issues.

### `pipeline.py` — no changes needed

MLflow's `autolog()` hooks globally. The existing `pipeline.py` code stays exactly as-is. Both tracers fire on the same `agent.astream()` calls.

### Risk mitigation

- If MLflow tracking server is unreachable, `autolog()` logs warnings but does not crash. The pipeline continues normally.
- If `MLFLOW_TRACKING_URI` is unset, the `if` block never executes. Zero behavioral change. No MLflow imports at runtime.
- `pipeline.py` is untouched — MLflow hooks externally via the global autolog mechanism.

## What Gets Traced

Both LangFuse and MLflow auto-capture the same hierarchy:

```
▼ ops_manager (TRACE / SPAN)
  ├─ LLM  claude-sonnet-4-6 — classify domain
  ├─ TOOL read_file — skills/error-classifier/SKILL.md
  ├─ TOOL read_file — incident.json
  ├─ TOOL task — delegate to sre_linux
  │   ▼ sre_linux (CHILD SPAN)
  │     ├─ TOOL read_file — skills/analyze-linux-failure/SKILL.md
  │     ├─ TOOL read_file — incident.json
  │     ├─ LLM  claude-sonnet-4-6 — root cause analysis
  │     └─ LLM  claude-sonnet-4-6 — format analysis
  ├─ TOOL task — delegate to reviewer
  │   ▼ reviewer (CHILD SPAN)
  │     └─ LLM  claude-3-5-haiku — validate ticket quality
  └─ LLM  claude-sonnet-4-6 — final TicketPayload
```

MLflow presents this as nested spans in the MLflow UI's "Traces" tab. LangFuse presents the same data in its trace waterfall view.

## Athena Helm Chart Changes

### `values.yaml`

```yaml
mlflow:
  trackingUri: ""
  experimentName: ""
```

### `templates/deployment.yaml`

```yaml
{{- if .Values.mlflow.trackingUri }}
- name: MLFLOW_TRACKING_URI
  value: {{ .Values.mlflow.trackingUri | quote }}
- name: MLFLOW_EXPERIMENT_NAME
  value: {{ .Values.mlflow.experimentName | quote }}
{{- end }}
```

No secrets needed — MLflow tracking URI and experiment name are not sensitive (no auth on the dev server).

## Cluster Workload: `ocp4_workload_mlflow_cluster`

**Collection:** `rhpds.deepagents_aiops`

### What it deploys

- MLflow tracking server via Helm chart
- PostgreSQL backend for experiment/trace metadata (single pod, 1Gi PVC)
- PVC for artifact storage
- OpenShift Route for UI access

### Namespace

`mlflow` (cluster-scoped, shared by all tenants)

### Resource footprint

- 2 pods: `mlflow` server + `mlflow-postgres`
- ~1Gi total memory
- 1Gi PVC for PostgreSQL, 5Gi PVC for artifacts

### Route

`mlflow.{{ openshift_cluster_ingress_domain }}`

### Helm chart

Create a minimal chart in the deployer repo at `helm/mlflow/` with:
- MLflow Deployment (single container, `ghcr.io/mlflow/mlflow:latest`)
- PostgreSQL Deployment + PVC (Bitnami PostgreSQL subchart or standalone)
- Service + Route
- ConfigMap for MLflow server configuration (`--backend-store-uri postgresql://...` and `--default-artifact-root /mlflow/artifacts`)

### Role structure

```
roles/ocp4_workload_mlflow_cluster/
├── defaults/main.yml      # Chart version, image, resource limits
├── meta/main.yml
└── tasks/
    ├── main.yml
    ├── workload.yml        # Create namespace, helm install
    └── remove_workload.yml # Cleanup
```

### agnosticv wiring

Add to cluster `common.yaml` workloads list. Only activated in `dev.yaml`:

```yaml
# dev.yaml only
workloads:
  # ... existing workloads ...
  - rhpds.deepagents_aiops.ocp4_workload_mlflow_cluster
```

## Tenant Workload: `ocp4_workload_mlflow_tenant`

**Collection:** `rhpds.deepagents_aiops`

### What it does

1. Creates an MLflow experiment via REST API:
   ```
   POST http://mlflow.mlflow.svc.cluster.local:5000/api/2.0/mlflow/experiments/create
   {"name": "{{ ocp4_workload_username }}-agentic"}
   ```
2. Passes MLflow config to the Athena tenant workload via env vars

### Env vars for Athena

- `MLFLOW_TRACKING_URI`: `http://mlflow.mlflow.svc.cluster.local:5000`
- `MLFLOW_EXPERIMENT_NAME`: `{{ ocp4_workload_username }}-agentic`

### Role structure

```
roles/ocp4_workload_mlflow_tenant/
├── defaults/main.yml      # MLflow service URL, experiment naming pattern
├── meta/main.yml
└── tasks/
    ├── main.yml
    ├── workload.yml        # Create experiment, set vars
    └── remove_workload.yml # Delete experiment
```

### Dependency

Runs after `ocp4_workload_mlflow_cluster` and before `ocp4_workload_athena_tenant`.

### agnosticv wiring

Add to tenant `common.yaml` workloads list. Only activated in `dev.yaml`:

```yaml
# dev.yaml only, between langfuse_tenant and athena_tenant
workloads:
  # ... existing workloads ...
  - rhpds.deepagents_aiops.ocp4_workload_mlflow_tenant
  # ... athena_tenant follows ...
```

### Athena tenant workload update

Modify `ocp4_workload_athena_tenant` to accept and pass through the two MLflow env vars when set. Same conditional pattern already used for LangFuse vars.

## Showroom Tab

Add to tenant `common.yaml` showroom tab configuration (dev only):

```yaml
- name: MLflow
  url: 'https://mlflow.{{ openshift_cluster_ingress_domain }}'
```

Placed after the LangFuse tab for side-by-side comparison.

## Files Changed

### Athena (`athena-aiops-deep-agent`)

| File | Change |
|------|--------|
| `pyproject.toml` | Add `mlflow>=2.15` |
| `athena/config.py` | Add 2 optional MLflow settings |
| `athena/app.py` | Register MLflow autolog in lifespan (guarded by env var) |

### Athena Helm chart (`deploy/helm/athena/`)

| File | Change |
|------|--------|
| `values.yaml` | Add optional `mlflow.*` values |
| `templates/deployment.yaml` | Wire MLflow env vars into container |

### Deployer (`deepagents-aiops`)

| File | Change |
|------|--------|
| `roles/ocp4_workload_mlflow_cluster/` | New role: deploy shared MLflow server |
| `roles/ocp4_workload_mlflow_tenant/` | New role: create per-tenant experiment |
| `roles/ocp4_workload_athena_tenant/defaults/main.yml` | Add MLflow env var defaults |
| `roles/ocp4_workload_athena_tenant/tasks/workload.yml` | Wire MLflow vars to Athena |

### agnosticv (worktree: `kira-frontend-0.11.1`)

| File | Change |
|------|--------|
| `summit-2026/lb2645-agentic-devops-cluster/dev.yaml` | Add `ocp4_workload_mlflow_cluster` workload |
| `summit-2026/lb2645-agentic-devops-tenant/dev.yaml` | Add `ocp4_workload_mlflow_tenant` workload |
| `summit-2026/lb2645-agentic-devops-tenant/dev.yaml` | Add MLflow showroom tab |

## Testing

### Athena unit

- Verify Athena starts normally with MLflow env vars set
- Verify Athena starts normally with MLflow env vars unset (no tracing, no errors)
- Verify both LangFuse and MLflow traces appear on a single pipeline run

### Integration

- Deploy MLflow cluster workload to a test cluster
- Deploy MLflow tenant workload for a test user
- Trigger "Install Python 3.14" failed job
- Verify trace appears in both LangFuse UI and MLflow UI with the expected hierarchy
- Verify Kira ticket and Rocket.Chat notification still work normally
- Verify Athena continues working when MLflow server is unreachable (graceful degradation)

### Production safety

- Verify `event.yaml` has no MLflow workloads
- Verify Athena on production clusters has no `MLFLOW_TRACKING_URI` set
- Verify zero behavioral change in production

## Relationship to Existing Specs

- **Extends**: `2026-05-02-langfuse-tracing-design.md` — adds MLflow as a second backend using the same opt-in pattern
- **Does not replace**: LangFuse remains the primary tracing backend in production
- **Future**: When MLflow is validated, a separate migration spec will cover LangFuse removal
