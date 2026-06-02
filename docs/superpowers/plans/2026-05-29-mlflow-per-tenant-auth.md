# MLflow Per-Tenant Authentication Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add basic HTTP authentication to the shared MLflow server so each tenant gets a `user-{{guid}}` login and can only see their own experiment.

**Architecture:** Enable MLflow's built-in basic auth (`--app-name basic-auth`) on the cluster deployment with `default_permission = NO_PERMISSIONS`. The tenant deployer creates per-user accounts and grants experiment permissions via the MLflow REST API. Athena authenticates using `MLFLOW_TRACKING_USERNAME` / `MLFLOW_TRACKING_PASSWORD` env vars.

**Tech Stack:** Ansible roles (deepagents-aiops), Helm chart (athena-aiops-deep-agent), agnosticv catalog (dev.yaml), MLflow REST API

**Repos:**
- `deepagents-aiops` at `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/` (branch: `main`)
- `athena-aiops-deep-agent` at `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent/` (branch: `main`)
- `agnosticv` at `/Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1/` (branch: `feat/kira-frontend-0.11.1`)

**Spec:** `docs/superpowers/specs/2026-05-29-mlflow-per-tenant-auth-design.md`

---

## File Map

### deepagents-aiops (Ansible deployer)

| File | Action | Purpose |
|------|--------|---------|
| `roles/ocp4_workload_mlflow_cluster/defaults/main.yml` | Modify | Add admin username/password defaults |
| `roles/ocp4_workload_mlflow_cluster/tasks/workload.yml` | Modify | Add ConfigMap, Helm extraArgs/extraVolumes, admin verification step |
| `roles/ocp4_workload_mlflow_tenant/defaults/main.yml` | Modify | Add tenant username/password, admin credentials defaults |
| `roles/ocp4_workload_mlflow_tenant/tasks/workload.yml` | Modify | Add auth headers to experiment create, add user creation + permission grant |
| `roles/ocp4_workload_mlflow_tenant/tasks/remove_workload.yml` | Modify | Add auth headers to existing tasks, add user deletion |
| `roles/ocp4_workload_athena_tenant/defaults/main.yml` | Modify | Add MLflow username/password defaults |
| `roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2` | Modify | Wire MLflow username/password into Helm values |

### athena-aiops-deep-agent (Athena service)

| File | Action | Purpose |
|------|--------|---------|
| `deploy/helm/athena/values.yaml` | Modify | Add `mlflow.username`, `mlflow.password` |
| `deploy/helm/athena/templates/deployment.yaml` | Modify | Wire `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD` env vars |
| `athena/config.py` | Modify | Add optional `mlflow_tracking_username`, `mlflow_tracking_password` |

### agnosticv (catalog)

| File | Action | Purpose |
|------|--------|---------|
| `summit-2026/lb2645-agentic-devops-tenant/dev.yaml` | Modify | Add MLflow username/password variables |

---

### Task 1: Cluster Role — Add Auth Config and Enable Basic Auth

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_mlflow_cluster/defaults/main.yml`
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_mlflow_cluster/tasks/workload.yml`

- [ ] **Step 1: Add admin credential defaults**

In `roles/ocp4_workload_mlflow_cluster/defaults/main.yml`, append after the existing retry configuration block:

```yaml
# Authentication (basic-auth)
ocp4_workload_mlflow_cluster_admin_username: admin
ocp4_workload_mlflow_cluster_admin_password: "{{ common_admin_password | default('mlflow-admin') }}"
```

- [ ] **Step 2: Add auth ConfigMap task to workload.yml**

In `roles/ocp4_workload_mlflow_cluster/tasks/workload.yml`, insert a new section **after step 1 (Create namespace)** and **before step 2 (Pre-create service accounts)**. Renumber nothing — use a comment header "1b" to avoid rewriting the whole file:

```yaml
# -------------------------------------------------------------------
# 1b. Create auth configuration ConfigMap
# -------------------------------------------------------------------
- name: Create MLflow auth config
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: v1
      kind: ConfigMap
      metadata:
        name: mlflow-auth-config
        namespace: "{{ ocp4_workload_mlflow_cluster_namespace }}"
      data:
        auth_config.ini: |
          [mlflow]
          default_permission = NO_PERMISSIONS
          database_uri = postgresql://{{ ocp4_workload_mlflow_cluster_postgres_user }}:{{ ocp4_workload_mlflow_cluster_postgres_password }}@mlflow-postgresql:5432/{{ ocp4_workload_mlflow_cluster_postgres_database }}
          admin_username = {{ ocp4_workload_mlflow_cluster_admin_username }}
          admin_password = {{ ocp4_workload_mlflow_cluster_admin_password }}
          authorization_function = mlflow.server.auth:authenticate_request_basic_auth
```

- [ ] **Step 3: Update Helm values to enable basic auth**

In `roles/ocp4_workload_mlflow_cluster/tasks/workload.yml`, replace the existing `Deploy MLflow via Helm` task's `values:` block. The changes are:
1. Add `extraArgs` with `app-name: basic-auth`
2. Add `MLFLOW_AUTH_CONFIG_PATH` and `MLFLOW_FLASK_SERVER_SECRET_KEY` to `extraEnvVars`
3. Add `extraVolumes` and `extraVolumeMounts`

Replace the entire `values:` block in the Helm task:

```yaml
    values:
      backendStore:
        databaseConnectionCheck: true
      artifactRoot:
        proxiedArtifactStorage: true
      postgresql:
        enabled: true
        auth:
          username: "{{ ocp4_workload_mlflow_cluster_postgres_user }}"
          password: "{{ ocp4_workload_mlflow_cluster_postgres_password }}"
          database: "{{ ocp4_workload_mlflow_cluster_postgres_database }}"
      resources:
        requests:
          cpu: "{{ ocp4_workload_mlflow_cluster_cpu_request }}"
          memory: "{{ ocp4_workload_mlflow_cluster_memory_request }}"
        limits:
          cpu: "{{ ocp4_workload_mlflow_cluster_cpu_limit }}"
          memory: "{{ ocp4_workload_mlflow_cluster_memory_limit }}"
      extraArgs:
        app-name: basic-auth
      extraEnvVars:
        MLFLOW_SERVER_DISABLE_SECURITY_MIDDLEWARE: "true"
        MLFLOW_AUTH_CONFIG_PATH: /etc/mlflow/auth_config.ini
        MLFLOW_FLASK_SERVER_SECRET_KEY: "{{ ocp4_workload_mlflow_cluster_admin_password }}"
      extraVolumes:
        - name: auth-config
          configMap:
            name: mlflow-auth-config
      extraVolumeMounts:
        - name: auth-config
          mountPath: /etc/mlflow
          readOnly: true
      serviceMonitor:
        enabled: false
```

- [ ] **Step 4: Add admin verification step after health check**

In `roles/ocp4_workload_mlflow_cluster/tasks/workload.yml`, insert a new section **after step 9 (Verify MLflow API)** and **before step 10 (Save connection info)**:

```yaml
# -------------------------------------------------------------------
# 9b. Verify MLflow auth is operational
# -------------------------------------------------------------------
- name: Verify MLflow basic auth is operational
  ansible.builtin.uri:
    url: "{{ _ocp4_workload_mlflow_cluster_url }}/api/2.0/mlflow/users/get?username={{ ocp4_workload_mlflow_cluster_admin_username }}"
    method: GET
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_cluster_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_cluster_admin_password }}"
    validate_certs: false
    status_code: 200
  register: r_mlflow_auth_check
  retries: 30
  delay: 10
  until: r_mlflow_auth_check is succeeded
```

- [ ] **Step 5: Update saved connection info to include admin credentials**

In the existing `Save MLflow connection info` task, add the admin credentials:

```yaml
- name: Save MLflow connection info
  agnosticd.core.agnosticd_user_info:
    data:
      mlflow_url: "{{ _ocp4_workload_mlflow_cluster_url }}"
      mlflow_internal_url: "{{ _ocp4_workload_mlflow_cluster_internal_url }}"
      mlflow_admin_username: "{{ ocp4_workload_mlflow_cluster_admin_username }}"
      mlflow_admin_password: "{{ ocp4_workload_mlflow_cluster_admin_password }}"
```

- [ ] **Step 6: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_mlflow_cluster/defaults/main.yml roles/ocp4_workload_mlflow_cluster/tasks/workload.yml
git commit -m "feat: enable MLflow basic auth with per-tenant isolation"
```

---

### Task 2: Tenant Role — Add Auth Headers, User Creation, and Permission Grant

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_mlflow_tenant/defaults/main.yml`
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_mlflow_tenant/tasks/workload.yml`

- [ ] **Step 1: Add tenant and admin credential defaults**

In `roles/ocp4_workload_mlflow_tenant/defaults/main.yml`, append after the existing retry configuration:

```yaml
# Authentication
ocp4_workload_mlflow_tenant_admin_username: admin
ocp4_workload_mlflow_tenant_admin_password: "{{ common_admin_password | default('mlflow-admin') }}"
ocp4_workload_mlflow_tenant_username: "user-{{ guid }}"
ocp4_workload_mlflow_tenant_password: "{{ common_admin_password | default('openshift') }}"
```

- [ ] **Step 2: Rewrite workload.yml with auth headers and user management**

Replace the entire contents of `roles/ocp4_workload_mlflow_tenant/tasks/workload.yml`:

```yaml
---
# ===================================================================
# Create per-tenant MLflow experiment, user, and permissions
# ===================================================================

# -------------------------------------------------------------------
# 1. Create MLflow experiment via REST API (authenticated as admin)
# -------------------------------------------------------------------
- name: Create MLflow experiment for tenant
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/experiments/create"
    method: POST
    body_format: json
    body:
      name: "{{ ocp4_workload_mlflow_tenant_experiment_name }}"
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
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
# 2. Look up experiment ID (needed for permission grant)
# -------------------------------------------------------------------
- name: Look up MLflow experiment by name
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/experiments/get-by-name?experiment_name={{ ocp4_workload_mlflow_tenant_experiment_name | urlencode }}"
    method: GET
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
    status_code: 200
    validate_certs: false
  register: r_experiment_lookup

- name: Set experiment ID fact
  ansible.builtin.set_fact:
    _ocp4_workload_mlflow_tenant_experiment_id: "{{ r_experiment_lookup.json.experiment.experiment_id }}"

# -------------------------------------------------------------------
# 3. Create tenant user
# -------------------------------------------------------------------
- name: Create MLflow user for tenant
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/users/create"
    method: POST
    body_format: json
    body:
      username: "{{ ocp4_workload_mlflow_tenant_username }}"
      password: "{{ ocp4_workload_mlflow_tenant_password }}"
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
    status_code:
      - 200
      - 409
    validate_certs: false
  register: r_mlflow_user
  changed_when: r_mlflow_user.status == 200

- name: Log MLflow user creation
  ansible.builtin.debug:
    msg: >-
      MLflow user '{{ ocp4_workload_mlflow_tenant_username }}'
      {{ 'created' if r_mlflow_user.status == 200 else 'already exists' }}

# -------------------------------------------------------------------
# 4. Grant tenant user MANAGE permission on their experiment
# -------------------------------------------------------------------
- name: Grant tenant MANAGE permission on experiment
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/experiments/permissions/create"
    method: POST
    body_format: json
    body:
      experiment_id: "{{ _ocp4_workload_mlflow_tenant_experiment_id }}"
      username: "{{ ocp4_workload_mlflow_tenant_username }}"
      permission: MANAGE
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
    status_code:
      - 200
      - 409
    validate_certs: false
  register: r_mlflow_permission
  changed_when: r_mlflow_permission.status == 200

# -------------------------------------------------------------------
# 5. Save connection info for downstream roles
# -------------------------------------------------------------------
- name: Save MLflow tenant info to agnosticd_user_info
  agnosticd.core.agnosticd_user_info:
    data:
      mlflow_tracking_uri: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}"
      mlflow_experiment_name: "{{ ocp4_workload_mlflow_tenant_experiment_name }}"
      mlflow_username: "{{ ocp4_workload_mlflow_tenant_username }}"
      mlflow_password: "{{ ocp4_workload_mlflow_tenant_password }}"
```

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_mlflow_tenant/defaults/main.yml roles/ocp4_workload_mlflow_tenant/tasks/workload.yml
git commit -m "feat: create per-tenant MLflow user with experiment permissions"
```

---

### Task 3: Tenant Cleanup — Add Auth Headers and User Deletion

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_mlflow_tenant/tasks/remove_workload.yml`

- [ ] **Step 1: Rewrite remove_workload.yml with auth and user deletion**

Replace the entire contents of `roles/ocp4_workload_mlflow_tenant/tasks/remove_workload.yml`:

```yaml
---
# MLflow experiments cannot be permanently deleted via API (only soft-deleted).
# The shared server cleanup happens in ocp4_workload_mlflow_cluster remove.

# -------------------------------------------------------------------
# 1. Look up experiment
# -------------------------------------------------------------------
- name: Look up MLflow experiment by name
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/experiments/get-by-name?experiment_name={{ ocp4_workload_mlflow_tenant_experiment_name | urlencode }}"
    method: GET
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
    status_code:
      - 200
      - 404
    validate_certs: false
  register: r_experiment_lookup
  ignore_errors: true

# -------------------------------------------------------------------
# 2. Soft-delete experiment
# -------------------------------------------------------------------
- name: Delete MLflow experiment for tenant (soft delete)
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/experiments/delete"
    method: POST
    body_format: json
    body:
      experiment_id: "{{ r_experiment_lookup.json.experiment.experiment_id }}"
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
    status_code:
      - 200
      - 404
    validate_certs: false
  when:
    - r_experiment_lookup is succeeded
    - r_experiment_lookup.status == 200
  ignore_errors: true

# -------------------------------------------------------------------
# 3. Delete tenant user
# -------------------------------------------------------------------
- name: Delete MLflow tenant user
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/users/delete?username={{ ocp4_workload_mlflow_tenant_username | urlencode }}"
    method: DELETE
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
    status_code:
      - 200
      - 404
    validate_certs: false
  ignore_errors: true

- name: Log MLflow experiment cleanup
  ansible.builtin.debug:
    msg: "MLflow cleanup for tenant {{ ocp4_workload_mlflow_tenant_experiment_name }} — experiment soft-deleted, user deleted"
```

- [ ] **Step 2: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_mlflow_tenant/tasks/remove_workload.yml
git commit -m "feat: add auth headers and user deletion to MLflow tenant cleanup"
```

---

### Task 4: Athena Tenant Deployer — Wire MLflow Credentials

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_athena_tenant/defaults/main.yml`
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2`

- [ ] **Step 1: Add MLflow credential defaults**

In `roles/ocp4_workload_athena_tenant/defaults/main.yml`, find the existing MLflow section:

```yaml
# MLflow tracing (opt-in — leave empty to disable)
ocp4_workload_athena_tenant_mlflow_tracking_uri: ""
ocp4_workload_athena_tenant_mlflow_experiment_name: ""
```

Replace it with:

```yaml
# MLflow tracing (opt-in — leave empty to disable)
ocp4_workload_athena_tenant_mlflow_tracking_uri: ""
ocp4_workload_athena_tenant_mlflow_experiment_name: ""
ocp4_workload_athena_tenant_mlflow_username: ""
ocp4_workload_athena_tenant_mlflow_password: ""
```

- [ ] **Step 2: Wire MLflow credentials in Helm values template**

In `roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2`, find the existing MLflow block:

```yaml
{% if ocp4_workload_athena_tenant_mlflow_tracking_uri | default('') | length > 0 %}
mlflow:
  trackingUri: "{{ ocp4_workload_athena_tenant_mlflow_tracking_uri }}"
  experimentName: "{{ ocp4_workload_athena_tenant_mlflow_experiment_name }}"
{% endif %}
```

Replace it with:

```yaml
{% if ocp4_workload_athena_tenant_mlflow_tracking_uri | default('') | length > 0 %}
mlflow:
  trackingUri: "{{ ocp4_workload_athena_tenant_mlflow_tracking_uri }}"
  experimentName: "{{ ocp4_workload_athena_tenant_mlflow_experiment_name }}"
  username: "{{ ocp4_workload_athena_tenant_mlflow_username }}"
  password: "{{ ocp4_workload_athena_tenant_mlflow_password }}"
{% endif %}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/defaults/main.yml roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2
git commit -m "feat: wire MLflow credentials through Athena tenant deployer"
```

---

### Task 5: Athena Helm Chart — Add MLflow Credential Env Vars

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent/deploy/helm/athena/values.yaml`
- Modify: `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent/deploy/helm/athena/templates/deployment.yaml`

- [ ] **Step 1: Add username/password to Helm values**

In `deploy/helm/athena/values.yaml`, find the existing `mlflow:` section:

```yaml
mlflow:
  trackingUri: ""
  experimentName: ""
```

Replace it with:

```yaml
mlflow:
  trackingUri: ""
  experimentName: ""
  username: ""
  password: ""
```

- [ ] **Step 2: Wire env vars in deployment template**

In `deploy/helm/athena/templates/deployment.yaml`, find the existing MLflow conditional block:

```yaml
            {{- if .Values.mlflow.trackingUri }}
            - name: MLFLOW_TRACKING_URI
              value: {{ .Values.mlflow.trackingUri | quote }}
            - name: MLFLOW_EXPERIMENT_NAME
              value: {{ .Values.mlflow.experimentName | quote }}
            {{- end }}
```

Replace it with:

```yaml
            {{- if .Values.mlflow.trackingUri }}
            - name: MLFLOW_TRACKING_URI
              value: {{ .Values.mlflow.trackingUri | quote }}
            - name: MLFLOW_EXPERIMENT_NAME
              value: {{ .Values.mlflow.experimentName | quote }}
            {{- if .Values.mlflow.username }}
            - name: MLFLOW_TRACKING_USERNAME
              value: {{ .Values.mlflow.username | quote }}
            - name: MLFLOW_TRACKING_PASSWORD
              value: {{ .Values.mlflow.password | quote }}
            {{- end }}
            {{- end }}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
git add deploy/helm/athena/values.yaml deploy/helm/athena/templates/deployment.yaml
git commit -m "feat: add MLflow credential env vars to Athena Helm chart"
```

---

### Task 6: Athena Config — Add Optional MLflow Credential Settings

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent/athena/config.py`

- [ ] **Step 1: Add MLflow credential fields**

In `athena/config.py`, find the existing MLflow section:

```python
    # MLflow tracing (opt-in — if unset, no tracing)
    mlflow_tracking_uri: str | None = None
    mlflow_experiment_name: str | None = None
```

Replace it with:

```python
    # MLflow tracing (opt-in — if unset, no tracing)
    mlflow_tracking_uri: str | None = None
    mlflow_experiment_name: str | None = None
    mlflow_tracking_username: str | None = None
    mlflow_tracking_password: str | None = None
```

Note: The MLflow Python client reads `MLFLOW_TRACKING_USERNAME` and `MLFLOW_TRACKING_PASSWORD` directly from environment variables. These fields exist for validation/documentation — the client does not read them from our Settings object.

- [ ] **Step 2: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
git add athena/config.py
git commit -m "feat: add optional MLflow credential settings to config"
```

---

### Task 7: agnosticv — Wire MLflow Credentials in dev.yaml

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1/summit-2026/lb2645-agentic-devops-tenant/dev.yaml`

- [ ] **Step 1: Add MLflow credential variables**

In `dev.yaml`, find the existing MLflow wiring block:

```yaml
# Wire MLflow to Athena
ocp4_workload_athena_tenant_mlflow_tracking_uri: "http://mlflow.mlflow.svc.cluster.local"
ocp4_workload_athena_tenant_mlflow_experiment_name: "{{ ocp4_workload_username }}-agentic"
```

Replace it with:

```yaml
# Wire MLflow to Athena
ocp4_workload_athena_tenant_mlflow_tracking_uri: "http://mlflow.mlflow.svc.cluster.local"
ocp4_workload_athena_tenant_mlflow_experiment_name: "{{ ocp4_workload_username }}-agentic"
ocp4_workload_athena_tenant_mlflow_username: "user-{{ guid }}"
ocp4_workload_athena_tenant_mlflow_password: "{{ common_admin_password }}"
```

- [ ] **Step 2: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1
git add summit-2026/lb2645-agentic-devops-tenant/dev.yaml
git commit -m "feat: add MLflow per-tenant credentials to dev.yaml"
```

---

### Task 8: Rebuild Athena Image and Push All Repos

**Files:** No file changes — deployment steps only.

- [ ] **Step 1: Run linter on Athena code**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
uv run ruff check . && uv run ruff format --check .
```

Expected: No errors.

- [ ] **Step 2: Run tests**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
uv run pytest
```

Expected: All tests pass.

- [ ] **Step 3: Rebuild and push Athena image**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
podman build --platform linux/amd64 -t quay.io/rhpds/athena-aiops:latest -f Dockerfile .
podman push quay.io/rhpds/athena-aiops:latest
```

- [ ] **Step 4: Push all repos**

```bash
# athena-aiops-deep-agent
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
git pull --rebase && git push

# deepagents-aiops
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git pull --rebase && git push

# agnosticv
cd /Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1
git pull --rebase origin feat/kira-frontend-0.11.1 && git push
```

- [ ] **Step 5: Verify all repos are pushed**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent && git status
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && git status
cd /Users/tok/Dropbox/PARAL/Resources/repos/agnosticv/worktrees/kira-frontend-0.11.1 && git status
```

Expected: All three show "up to date with origin".

---

## Deployment Verification Checklist

After deploying to cluster-b8xxn:

1. `helm upgrade` completes — MLflow pod starts without crash (validates `--app-name basic-auth` with gunicorn)
2. MLflow UI at `https://mlflow-mlflow.apps.cluster-b8xxn...` shows login prompt
3. Admin can log in with `admin` / `<common_admin_password>`
4. After tenant deploy: `user-<guid>` can log in and sees only their experiment
5. Athena pod starts with `MLFLOW_TRACKING_USERNAME` / `MLFLOW_TRACKING_PASSWORD` env vars
6. Trigger a failed AAP2 job → trace appears in MLflow under the tenant's experiment
7. Tenant remove cleans up user + experiment

## Rollback

If `--app-name basic-auth` crashes the pod with gunicorn:
1. Remove `extraArgs.app-name` from the Helm values
2. Remove `extraVolumes`/`extraVolumeMounts`
3. Keep the ConfigMap (harmless)
4. `helm upgrade` to redeploy without auth
5. Investigate env var alternative (`MLFLOW_APP_NAME`) or custom entrypoint
