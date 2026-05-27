# MLflow Dual-Tracing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add MLflow tracing alongside LangFuse in Athena so both fire on every pipeline run, deployed only to dev clusters.

**Architecture:** MLflow `autolog()` hooks LangChain globally while LangFuse's `CallbackHandler` fires per-run — both coexist without conflict. A shared cluster-wide MLflow tracking server (community Helm chart) serves all tenants, isolated by experiment name. Athena activates MLflow only when `MLFLOW_TRACKING_URI` is set (same opt-in pattern as LangFuse).

**Tech Stack:** MLflow >= 2.15, community-charts/mlflow Helm chart 1.8.x, Ansible (rhpds.deepagents_aiops collection), agnosticv

---

## File Structure

### Athena repo (`athena-aiops-deep-agent`)

| File | Responsibility |
|------|---------------|
| `pyproject.toml` | Add `mlflow>=2.15` dependency |
| `athena/config.py` | Add 2 optional MLflow settings |
| `athena/app.py` | MLflow autolog initialization in lifespan |
| `tests/test_config.py` | Test MLflow config fields |
| `deploy/helm/athena/values.yaml` | Add `mlflow.*` values block |
| `deploy/helm/athena/templates/deployment.yaml` | Wire MLflow env vars |

### Deployer repo (`deepagents-aiops`)

| File | Responsibility |
|------|---------------|
| `roles/ocp4_workload_mlflow_cluster/defaults/main.yml` | Cluster MLflow defaults |
| `roles/ocp4_workload_mlflow_cluster/tasks/main.yml` | Action router |
| `roles/ocp4_workload_mlflow_cluster/tasks/workload.yml` | Deploy MLflow via Helm |
| `roles/ocp4_workload_mlflow_cluster/tasks/remove_workload.yml` | Cleanup |
| `roles/ocp4_workload_mlflow_tenant/defaults/main.yml` | Tenant defaults |
| `roles/ocp4_workload_mlflow_tenant/tasks/main.yml` | Action router |
| `roles/ocp4_workload_mlflow_tenant/tasks/workload.yml` | Create experiment |
| `roles/ocp4_workload_mlflow_tenant/tasks/remove_workload.yml` | Cleanup |
| `roles/ocp4_workload_athena_tenant/defaults/main.yml` | Add MLflow defaults |
| `roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2` | Wire MLflow values |

### agnosticv (worktree `kira-frontend-0.11.1`)

| File | Responsibility |
|------|---------------|
| `summit-2026/lb2645-agentic-devops-cluster/dev.yaml` | Add cluster workload |
| `summit-2026/lb2645-agentic-devops-tenant/dev.yaml` | Add tenant workload + showroom tab |

---

## Task 1: Athena Config — Add MLflow Settings

**Files:**
- Modify: `athena/config.py:40-43`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write the failing test for MLflow config fields**

Add to `tests/test_config.py`:

```python
def test_settings_optional_mlflow_defaults_to_none(monkeypatch: pytest.MonkeyPatch):
    env = _minimal_env()
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    settings = Settings()
    assert settings.mlflow_tracking_uri is None
    assert settings.mlflow_experiment_name is None


def test_settings_optional_mlflow_set(monkeypatch: pytest.MonkeyPatch):
    env = _minimal_env()
    env["mlflow_tracking_uri"] = "http://mlflow:5000"
    env["mlflow_experiment_name"] = "test-experiment"
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    settings = Settings()
    assert settings.mlflow_tracking_uri == "http://mlflow:5000"
    assert settings.mlflow_experiment_name == "test-experiment"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `Settings` has no attribute `mlflow_tracking_uri`

- [ ] **Step 3: Add MLflow settings to config.py**

Add after the LangFuse settings block (after line 43) in `athena/config.py`:

```python
    # MLflow tracing (opt-in — if unset, no tracing)
    mlflow_tracking_uri: str | None = None
    mlflow_experiment_name: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: All PASS

- [ ] **Step 5: Run full test suite to check for regressions**

Run: `uv run pytest -v`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add athena/config.py tests/test_config.py
git commit -m "feat: add MLflow config settings (opt-in, defaults to None)"
```

---

## Task 2: Athena Dependency — Add mlflow to pyproject.toml

**Files:**
- Modify: `pyproject.toml:6-21`

- [ ] **Step 1: Add mlflow dependency**

Add `"mlflow>=2.15",` to the `dependencies` list in `pyproject.toml`, after the `langfuse` entry (line 20):

```toml
    "langfuse>=2.0",
    "mlflow>=2.15",
```

- [ ] **Step 2: Sync dependencies**

Run: `uv sync`
Expected: mlflow and its transitive dependencies install successfully

- [ ] **Step 3: Verify import works**

Run: `uv run python -c "import mlflow; print(mlflow.__version__)"`
Expected: Prints version >= 2.15

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps: add mlflow>=2.15 for dual tracing"
```

---

## Task 3: Athena App — MLflow Autolog in Lifespan

**Files:**
- Modify: `athena/app.py:36-45`

- [ ] **Step 1: Add MLflow initialization after the LangFuse block**

In `athena/app.py`, add the following block after the LangFuse initialization (after line 45, which is `logger.info("LangFuse tracing enabled → %s", settings.langfuse_host)`):

```python
    # MLflow tracing (opt-in)
    if settings.mlflow_tracking_uri:
        import mlflow
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment_name or "athena-default")
        mlflow.langchain.autolog()
        logger.info("MLflow tracing enabled → %s", settings.mlflow_tracking_uri)
```

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -v`
Expected: All PASS — the new code is guarded by `if settings.mlflow_tracking_uri` so it never fires in tests (no env var set)

- [ ] **Step 3: Run lint**

Run: `uv run ruff check athena/app.py`
Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add athena/app.py
git commit -m "feat: add MLflow autolog in lifespan (opt-in via MLFLOW_TRACKING_URI)"
```

---

## Task 4: Athena Helm Chart — Add MLflow Values and Env Vars

**Files:**
- Modify: `deploy/helm/athena/values.yaml:31-34`
- Modify: `deploy/helm/athena/templates/deployment.yaml:115-125`

- [ ] **Step 1: Add mlflow values block to values.yaml**

Add after the `langfuse:` block (after line 34) in `deploy/helm/athena/values.yaml`:

```yaml
mlflow:
  trackingUri: ""
  experimentName: ""
```

- [ ] **Step 2: Add MLflow env vars to deployment.yaml**

Add after the LangFuse env var block (after line 125, which is `{{- end }}` closing the LangFuse conditional) in `deploy/helm/athena/templates/deployment.yaml`:

```yaml
            {{- if .Values.mlflow.trackingUri }}
            - name: MLFLOW_TRACKING_URI
              value: {{ .Values.mlflow.trackingUri | quote }}
            - name: MLFLOW_EXPERIMENT_NAME
              value: {{ .Values.mlflow.experimentName | quote }}
            {{- end }}
```

- [ ] **Step 3: Validate Helm template renders**

Run: `helm template test deploy/helm/athena/ 2>&1 | head -5`
Expected: Renders without errors. MLflow env vars should NOT appear (empty values).

Run: `helm template test deploy/helm/athena/ --set mlflow.trackingUri=http://mlflow:5000 --set mlflow.experimentName=test 2>&1 | grep -A2 MLFLOW`
Expected: Shows both `MLFLOW_TRACKING_URI` and `MLFLOW_EXPERIMENT_NAME` env vars

- [ ] **Step 4: Commit**

```bash
git add deploy/helm/athena/values.yaml deploy/helm/athena/templates/deployment.yaml
git commit -m "helm: add optional MLflow env vars to Athena chart"
```

---

## Task 5: Deployer — Cluster MLflow Workload Role

**Repo:** `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops`

**Files:**
- Create: `roles/ocp4_workload_mlflow_cluster/defaults/main.yml`
- Create: `roles/ocp4_workload_mlflow_cluster/tasks/main.yml`
- Create: `roles/ocp4_workload_mlflow_cluster/tasks/workload.yml`
- Create: `roles/ocp4_workload_mlflow_cluster/tasks/remove_workload.yml`

- [ ] **Step 1: Create role directory structure**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
mkdir -p roles/ocp4_workload_mlflow_cluster/{defaults,tasks}
```

- [ ] **Step 2: Create defaults/main.yml**

Write `roles/ocp4_workload_mlflow_cluster/defaults/main.yml`:

```yaml
---
# ===================================================================
# Role: ocp4_workload_mlflow_cluster
# Deploys a shared MLflow tracking server cluster-wide via Helm.
# ===================================================================

# Target namespace (cluster-scoped, shared by all tenants)
ocp4_workload_mlflow_cluster_namespace: mlflow

# Helm chart source (community-charts)
ocp4_workload_mlflow_cluster_helm_repo_name: community-charts
ocp4_workload_mlflow_cluster_helm_repo_url: https://community-charts.github.io/helm-charts
ocp4_workload_mlflow_cluster_helm_chart_version: "1.8.1"

# Helm release name
ocp4_workload_mlflow_cluster_release_name: mlflow

# MLflow image (use chart default unless override needed)
# ocp4_workload_mlflow_cluster_image: burakince/mlflow
# ocp4_workload_mlflow_cluster_image_tag: "3.7.0"

# PostgreSQL backend
ocp4_workload_mlflow_cluster_postgres_password: "{{ common_admin_password | default('mlflow-pg') }}"

# Resource limits
ocp4_workload_mlflow_cluster_memory_limit: 1Gi
ocp4_workload_mlflow_cluster_memory_request: 256Mi
ocp4_workload_mlflow_cluster_cpu_limit: "1"
ocp4_workload_mlflow_cluster_cpu_request: 100m

# Retry configuration
ocp4_workload_mlflow_cluster_deploy_retries: 60
ocp4_workload_mlflow_cluster_deploy_retry_delay: 10
```

- [ ] **Step 3: Create tasks/main.yml**

Write `roles/ocp4_workload_mlflow_cluster/tasks/main.yml`:

```yaml
---
- name: Running role ocp4_workload_mlflow_cluster
  ansible.builtin.debug:
    msg: "Running role ocp4_workload_mlflow_cluster"

- name: Run workload
  when: ACTION == "create" or ACTION == "provision"
  ansible.builtin.include_tasks: workload.yml

- name: Remove workload
  when: ACTION == "destroy" or ACTION == "remove"
  ansible.builtin.include_tasks: remove_workload.yml
```

- [ ] **Step 4: Create tasks/workload.yml**

Write `roles/ocp4_workload_mlflow_cluster/tasks/workload.yml`:

```yaml
---
# ===================================================================
# Deploy shared MLflow tracking server via community Helm chart
# ===================================================================

# -------------------------------------------------------------------
# 1. Create namespace
# -------------------------------------------------------------------
- name: Create MLflow namespace
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: v1
      kind: Namespace
      metadata:
        name: "{{ ocp4_workload_mlflow_cluster_namespace }}"

# -------------------------------------------------------------------
# 2. Add Helm repo
# -------------------------------------------------------------------
- name: Add community-charts Helm repository
  kubernetes.core.helm_repository:
    name: "{{ ocp4_workload_mlflow_cluster_helm_repo_name }}"
    repo_url: "{{ ocp4_workload_mlflow_cluster_helm_repo_url }}"

# -------------------------------------------------------------------
# 3. Deploy MLflow via Helm
# -------------------------------------------------------------------
- name: Deploy MLflow via Helm
  kubernetes.core.helm:
    name: "{{ ocp4_workload_mlflow_cluster_release_name }}"
    chart_ref: "{{ ocp4_workload_mlflow_cluster_helm_repo_name }}/mlflow"
    chart_version: "{{ ocp4_workload_mlflow_cluster_helm_chart_version }}"
    release_namespace: "{{ ocp4_workload_mlflow_cluster_namespace }}"
    values:
      backendStore:
        postgres:
          enabled: true
          password: "{{ ocp4_workload_mlflow_cluster_postgres_password }}"
      artifactRoot:
        proxiedArtifactStorage: true
      resources:
        requests:
          cpu: "{{ ocp4_workload_mlflow_cluster_cpu_request }}"
          memory: "{{ ocp4_workload_mlflow_cluster_memory_request }}"
        limits:
          cpu: "{{ ocp4_workload_mlflow_cluster_cpu_limit }}"
          memory: "{{ ocp4_workload_mlflow_cluster_memory_limit }}"
      serviceMonitor:
        enabled: false
    state: present
    wait: false

# -------------------------------------------------------------------
# 4. Create OpenShift Route for MLflow UI
# -------------------------------------------------------------------
- name: Create MLflow route
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: route.openshift.io/v1
      kind: Route
      metadata:
        name: mlflow
        namespace: "{{ ocp4_workload_mlflow_cluster_namespace }}"
      spec:
        to:
          kind: Service
          name: "{{ ocp4_workload_mlflow_cluster_release_name }}"
          weight: 100
        port:
          targetPort: http
        tls:
          termination: edge
          insecureEdgeTerminationPolicy: Redirect

# -------------------------------------------------------------------
# 5. Wait for MLflow to be ready
# -------------------------------------------------------------------
- name: Wait for MLflow deployment to be available
  kubernetes.core.k8s_info:
    api_version: apps/v1
    kind: Deployment
    name: "{{ ocp4_workload_mlflow_cluster_release_name }}"
    namespace: "{{ ocp4_workload_mlflow_cluster_namespace }}"
  register: r_mlflow_deploy
  retries: "{{ ocp4_workload_mlflow_cluster_deploy_retries }}"
  delay: "{{ ocp4_workload_mlflow_cluster_deploy_retry_delay }}"
  until:
    - r_mlflow_deploy.resources | length > 0
    - r_mlflow_deploy.resources[0].status.readyReplicas is defined
    - r_mlflow_deploy.resources[0].status.readyReplicas >= 1

# -------------------------------------------------------------------
# 6. Discover MLflow route URL
# -------------------------------------------------------------------
- name: Get MLflow route
  kubernetes.core.k8s_info:
    api_version: route.openshift.io/v1
    kind: Route
    name: mlflow
    namespace: "{{ ocp4_workload_mlflow_cluster_namespace }}"
  register: r_mlflow_route

- name: Set MLflow URL facts
  ansible.builtin.set_fact:
    _ocp4_workload_mlflow_cluster_url: "https://{{ r_mlflow_route.resources[0].spec.host }}"
    _ocp4_workload_mlflow_cluster_internal_url: "http://{{ ocp4_workload_mlflow_cluster_release_name }}.{{ ocp4_workload_mlflow_cluster_namespace }}.svc.cluster.local:5000"

# -------------------------------------------------------------------
# 7. Verify MLflow API is responsive
# -------------------------------------------------------------------
- name: Wait for MLflow API to be responsive
  ansible.builtin.uri:
    url: "{{ _ocp4_workload_mlflow_cluster_url }}/health"
    method: GET
    validate_certs: false
    status_code: 200
  register: r_mlflow_health
  retries: 30
  delay: 10
  until: r_mlflow_health is succeeded

# -------------------------------------------------------------------
# 8. Save connection info
# -------------------------------------------------------------------
- name: Save MLflow connection info
  agnosticd.core.agnosticd_user_info:
    data:
      mlflow_url: "{{ _ocp4_workload_mlflow_cluster_url }}"
      mlflow_internal_url: "{{ _ocp4_workload_mlflow_cluster_internal_url }}"
```

- [ ] **Step 5: Create tasks/remove_workload.yml**

Write `roles/ocp4_workload_mlflow_cluster/tasks/remove_workload.yml`:

```yaml
---
- name: Remove MLflow Helm release
  kubernetes.core.helm:
    name: "{{ ocp4_workload_mlflow_cluster_release_name }}"
    release_namespace: "{{ ocp4_workload_mlflow_cluster_namespace }}"
    state: absent
    wait: true

- name: Remove MLflow route
  kubernetes.core.k8s:
    api_version: route.openshift.io/v1
    kind: Route
    name: mlflow
    namespace: "{{ ocp4_workload_mlflow_cluster_namespace }}"
    state: absent

- name: Remove MLflow namespace
  kubernetes.core.k8s:
    api_version: v1
    kind: Namespace
    name: "{{ ocp4_workload_mlflow_cluster_namespace }}"
    state: absent
```

- [ ] **Step 6: Verify role structure**

Run: `find roles/ocp4_workload_mlflow_cluster -type f | sort`
Expected:
```
roles/ocp4_workload_mlflow_cluster/defaults/main.yml
roles/ocp4_workload_mlflow_cluster/tasks/main.yml
roles/ocp4_workload_mlflow_cluster/tasks/remove_workload.yml
roles/ocp4_workload_mlflow_cluster/tasks/workload.yml
```

- [ ] **Step 7: Lint with ansible-lint (if available)**

Run: `ansible-lint roles/ocp4_workload_mlflow_cluster/ 2>/dev/null || echo "ansible-lint not installed, skipping"`

- [ ] **Step 8: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_mlflow_cluster/
git commit -m "feat: add ocp4_workload_mlflow_cluster role (shared MLflow server)"
```

---

## Task 6: Deployer — Tenant MLflow Workload Role

**Repo:** `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops`

**Files:**
- Create: `roles/ocp4_workload_mlflow_tenant/defaults/main.yml`
- Create: `roles/ocp4_workload_mlflow_tenant/tasks/main.yml`
- Create: `roles/ocp4_workload_mlflow_tenant/tasks/workload.yml`
- Create: `roles/ocp4_workload_mlflow_tenant/tasks/remove_workload.yml`

- [ ] **Step 1: Create role directory structure**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
mkdir -p roles/ocp4_workload_mlflow_tenant/{defaults,tasks}
```

- [ ] **Step 2: Create defaults/main.yml**

Write `roles/ocp4_workload_mlflow_tenant/defaults/main.yml`:

```yaml
---
# ===================================================================
# Role: ocp4_workload_mlflow_tenant
# Creates a per-tenant MLflow experiment on the shared tracking server.
# ===================================================================

# MLflow tracking server (cluster-wide, deployed by ocp4_workload_mlflow_cluster)
ocp4_workload_mlflow_tenant_tracking_uri: "http://mlflow.mlflow.svc.cluster.local:5000"

# Experiment name (one per tenant)
ocp4_workload_mlflow_tenant_experiment_name: "{{ ocp4_workload_username }}-agentic"

# Retry configuration
ocp4_workload_mlflow_tenant_api_retries: 10
ocp4_workload_mlflow_tenant_api_retry_delay: 5
```

- [ ] **Step 3: Create tasks/main.yml**

Write `roles/ocp4_workload_mlflow_tenant/tasks/main.yml`:

```yaml
---
- name: Running role ocp4_workload_mlflow_tenant
  ansible.builtin.debug:
    msg: "Running role ocp4_workload_mlflow_tenant"

- name: Run workload
  when: ACTION == "create" or ACTION == "provision"
  ansible.builtin.include_tasks: workload.yml

- name: Remove workload
  when: ACTION == "destroy" or ACTION == "remove"
  ansible.builtin.include_tasks: remove_workload.yml
```

- [ ] **Step 4: Create tasks/workload.yml**

Write `roles/ocp4_workload_mlflow_tenant/tasks/workload.yml`:

```yaml
---
# ===================================================================
# Create per-tenant MLflow experiment on the shared tracking server
# ===================================================================

# -------------------------------------------------------------------
# 1. Create MLflow experiment via REST API
# -------------------------------------------------------------------
- name: Create MLflow experiment for tenant
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/experiments/create"
    method: POST
    body_format: json
    body:
      name: "{{ ocp4_workload_mlflow_tenant_experiment_name }}"
    status_code:
      - 200
      - 400
    validate_certs: false
  register: r_mlflow_experiment
  retries: "{{ ocp4_workload_mlflow_tenant_api_retries }}"
  delay: "{{ ocp4_workload_mlflow_tenant_api_retry_delay }}"
  until: r_mlflow_experiment is succeeded
  changed_when: r_mlflow_experiment.status == 200

- name: Log MLflow experiment creation
  ansible.builtin.debug:
    msg: >-
      MLflow experiment '{{ ocp4_workload_mlflow_tenant_experiment_name }}'
      {{ 'created' if r_mlflow_experiment.status == 200 else 'already exists' }}

# -------------------------------------------------------------------
# 2. Save connection info for downstream roles
# -------------------------------------------------------------------
- name: Save MLflow tenant info to agnosticd_user_info
  agnosticd.core.agnosticd_user_info:
    data:
      mlflow_tracking_uri: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}"
      mlflow_experiment_name: "{{ ocp4_workload_mlflow_tenant_experiment_name }}"
```

- [ ] **Step 5: Create tasks/remove_workload.yml**

Write `roles/ocp4_workload_mlflow_tenant/tasks/remove_workload.yml`:

```yaml
---
# MLflow experiments cannot be permanently deleted via API (only soft-deleted).
# The shared server cleanup happens in ocp4_workload_mlflow_cluster remove.
- name: Delete MLflow experiment for tenant (soft delete)
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/experiments/delete"
    method: POST
    body_format: json
    body:
      experiment_id: "{{ r_experiment_id.json.experiment.experiment_id }}"
    status_code:
      - 200
      - 404
    validate_certs: false
  when: r_experiment_id is defined and r_experiment_id.json.experiment is defined
  ignore_errors: true
  register: r_delete_experiment

- name: Log MLflow experiment cleanup
  ansible.builtin.debug:
    msg: "MLflow experiment cleanup for tenant {{ ocp4_workload_mlflow_tenant_experiment_name }} — soft delete attempted"
```

- [ ] **Step 6: Verify role structure**

Run: `find roles/ocp4_workload_mlflow_tenant -type f | sort`
Expected:
```
roles/ocp4_workload_mlflow_tenant/defaults/main.yml
roles/ocp4_workload_mlflow_tenant/tasks/main.yml
roles/ocp4_workload_mlflow_tenant/tasks/remove_workload.yml
roles/ocp4_workload_mlflow_tenant/tasks/workload.yml
```

- [ ] **Step 7: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_mlflow_tenant/
git commit -m "feat: add ocp4_workload_mlflow_tenant role (per-tenant experiment)"
```

---

## Task 7: Deployer — Wire MLflow into Athena Tenant Role

**Repo:** `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops`

**Files:**
- Modify: `roles/ocp4_workload_athena_tenant/defaults/main.yml:56-59`
- Modify: `roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2:54-59`

- [ ] **Step 1: Add MLflow defaults to Athena tenant role**

Add after the LangFuse defaults (after line 59) in `roles/ocp4_workload_athena_tenant/defaults/main.yml`:

```yaml
# MLflow tracing (opt-in — leave empty to disable)
ocp4_workload_athena_tenant_mlflow_tracking_uri: ""
ocp4_workload_athena_tenant_mlflow_experiment_name: ""
```

- [ ] **Step 2: Add MLflow to Helm values template**

Add after the LangFuse block (after line 59) in `roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2`:

```jinja2
{% if ocp4_workload_athena_tenant_mlflow_tracking_uri | default('') | length > 0 %}
mlflow:
  trackingUri: "{{ ocp4_workload_athena_tenant_mlflow_tracking_uri }}"
  experimentName: "{{ ocp4_workload_athena_tenant_mlflow_experiment_name }}"
{% endif %}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/defaults/main.yml roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2
git commit -m "feat: wire MLflow env vars into Athena tenant deployer"
```

---

## Task 8: agnosticv — Wire MLflow Workloads into Dev Config

**Repo:** `/Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1`

**Files:**
- Modify: `summit-2026/lb2645-agentic-devops-cluster/dev.yaml`
- Modify: `summit-2026/lb2645-agentic-devops-tenant/dev.yaml`

- [ ] **Step 1: Add MLflow cluster workload to cluster dev.yaml**

Replace the contents of `summit-2026/lb2645-agentic-devops-cluster/dev.yaml` with:

```yaml
---
# -------------------------------------------------------------------
# Dev overrides — single user for testing base infra
# Production base infra uses num_users: 0; tenants are provisioned separately
# -------------------------------------------------------------------

# -------------------------------------------------------------------
# MLflow cluster-wide tracking server (dev only)
# -------------------------------------------------------------------
workloads_post:
  - rhpds.deepagents_aiops.ocp4_workload_mlflow_cluster

# -------------------------------------------------------------------
# Babylon meta variables
# -------------------------------------------------------------------
__meta__:
  deployer:
    scm_ref: main
```

Note: `workloads_post` appends to the workloads list from common.yaml rather than replacing it. If the agnosticv deployer doesn't support `workloads_post`, use a full `workloads:` list that duplicates common.yaml's entries plus the MLflow workload at the end. Check with: `grep -r workloads_post /Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1/ --include='*.yaml' | head -5`

If `workloads_post` is not supported, instead add this to dev.yaml:

```yaml
# MLflow cluster-wide tracking server (dev only)
ocp4_workload_mlflow_cluster_enabled: true
```

And add the workload to the **common.yaml** workloads list with a conditional:
```yaml
  - rhpds.deepagents_aiops.ocp4_workload_mlflow_cluster
```
with `ocp4_workload_mlflow_cluster_enabled: false` in common.yaml defaults.

The implementer should check how other dev-only workloads are wired in the codebase before choosing the approach.

- [ ] **Step 2: Add MLflow tenant workload + showroom tab to tenant dev.yaml**

Add the following sections to `summit-2026/lb2645-agentic-devops-tenant/dev.yaml`, before the `__meta__:` block:

```yaml
# -------------------------------------------------------------------
# MLflow tenant experiment + Athena wiring (dev only)
# -------------------------------------------------------------------
# Extra workloads appended after common.yaml's list
# The MLflow tenant role must run between langfuse_tenant and athena_tenant
workloads:
  - agnosticd.namespaced_workloads.ocp4_workload_tenant_keycloak_user
  - agnosticd.namespaced_workloads.ocp4_workload_tenant_namespace
  - rhpds.litellm_virtual_keys.ocp4_workload_litellm_virtual_keys
  - agnosticd.namespaced_workloads.ocp4_workload_tenant_gitea_user
  - rhpds.deepagents_aiops.ocp4_workload_rhel_vm_tenant
  - rhpds.deepagents_aiops.ocp4_workload_aap2_tenant_config
  - rhpds.deepagents_aiops.ocp4_workload_kira_tenant
  - rhpds.deepagents_aiops.ocp4_workload_langfuse_tenant
  - rhpds.deepagents_aiops.ocp4_workload_mlflow_tenant
  - rhpds.deepagents_aiops.ocp4_workload_rocketchat_tenant
  - rhpds.deepagents_aiops.ocp4_workload_athena_tenant
  - agnosticd.showroom.ocp4_workload_showroom

# Wire MLflow to Athena
ocp4_workload_athena_tenant_mlflow_tracking_uri: "http://mlflow.mlflow.svc.cluster.local:5000"
ocp4_workload_athena_tenant_mlflow_experiment_name: "{{ ocp4_workload_username }}-agentic"

# Add MLflow tab to showroom (override common.yaml's showroom config)
ocp4_workload_showroom_content_ui_config: |
  type: showroom
  default_width: 40
  persist_url_state: true
  view_switcher:
    enabled: true
    default_mode: split
  tabs:
  - name: AAP2
    url: "https://aap-aap.{{ openshift_cluster_ingress_domain }}"
  - name: Kira
    url: "https://kira-frontend-{{ ocp4_workload_tenant_keycloak_username }}-agentic.{{ openshift_cluster_ingress_domain }}"
  - name: Terminal
    path: /terminal
    port: 443
  - name: RocketChat
    url: "https://rocketchat-{{ ocp4_workload_tenant_keycloak_username }}-agentic.{{ openshift_cluster_ingress_domain }}"
  - name: Gitea
    url: "https://gitea.{{ openshift_cluster_ingress_domain }}/user-{{ guid }}/agentic-devops-athena"
  - name: OpenShift Console
    url: "https://console-openshift-console.{{ openshift_cluster_ingress_domain }}"
  - name: LangFuse
    url: "https://langfuse-{{ ocp4_workload_tenant_keycloak_username }}-agentic.{{ openshift_cluster_ingress_domain }}"
  - name: MLflow
    url: "https://mlflow.{{ openshift_cluster_ingress_domain }}"
```

Note: The full `workloads:` list is repeated because dev.yaml overrides must replace the entire list to insert `ocp4_workload_mlflow_tenant` between `langfuse_tenant` and `rocketchat_tenant`. Similarly, `ocp4_workload_showroom_content_ui_config` is fully repeated with the MLflow tab added.

- [ ] **Step 3: Verify YAML is valid**

Run: `python3 -c "import yaml; yaml.safe_load(open('summit-2026/lb2645-agentic-devops-tenant/dev.yaml'))" && echo "YAML valid"`
Expected: "YAML valid"

Run: `python3 -c "import yaml; yaml.safe_load(open('summit-2026/lb2645-agentic-devops-cluster/dev.yaml'))" && echo "YAML valid"`
Expected: "YAML valid"

- [ ] **Step 4: Verify event.yaml has NO MLflow references**

Run: `grep -r mlflow summit-2026/lb2645-agentic-devops-*/event.yaml 2>/dev/null | wc -l`
Expected: 0

- [ ] **Step 5: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1
git add summit-2026/lb2645-agentic-devops-cluster/dev.yaml summit-2026/lb2645-agentic-devops-tenant/dev.yaml
git commit -m "feat: wire MLflow workloads into lb2645 dev config (cluster + tenant + showroom tab)"
```

---

## Task 9: Final Verification — Full Test Suite and Lint

**Repo:** `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent`

- [ ] **Step 1: Run full Athena test suite**

Run: `uv run pytest -v`
Expected: All PASS

- [ ] **Step 2: Run Athena linter**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: No errors

- [ ] **Step 3: Verify Helm template renders cleanly**

Run: `helm template test deploy/helm/athena/ --set aap2.url=test --set aap2.username=test --set aap2.password=test --set aap2.organization=test --set kira.url=test --set kira.apiKey=test --set rocketchat.url=test --set rocketchat.apiAuthToken=test --set rocketchat.apiUserId=test --set maas.apiBaseUrl=test --set maas.virtualKey=test 2>&1 | grep -c 'Error'`
Expected: 0

- [ ] **Step 4: Verify production safety — no MLflow env vars without config**

Run: `helm template test deploy/helm/athena/ --set aap2.url=test --set aap2.username=test --set aap2.password=test --set aap2.organization=test --set kira.url=test --set kira.apiKey=test --set rocketchat.url=test --set rocketchat.apiAuthToken=test --set rocketchat.apiUserId=test --set maas.apiBaseUrl=test --set maas.virtualKey=test 2>&1 | grep MLFLOW`
Expected: No output (MLflow env vars not present when trackingUri is empty)

- [ ] **Step 5: Verify MLflow env vars appear with config**

Run: `helm template test deploy/helm/athena/ --set aap2.url=test --set aap2.username=test --set aap2.password=test --set aap2.organization=test --set kira.url=test --set kira.apiKey=test --set rocketchat.url=test --set rocketchat.apiAuthToken=test --set rocketchat.apiUserId=test --set maas.apiBaseUrl=test --set maas.virtualKey=test --set mlflow.trackingUri=http://mlflow:5000 --set mlflow.experimentName=test 2>&1 | grep -A1 MLFLOW`
Expected: Shows `MLFLOW_TRACKING_URI` and `MLFLOW_EXPERIMENT_NAME`
