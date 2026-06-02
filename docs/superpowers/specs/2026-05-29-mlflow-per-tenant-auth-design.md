# MLflow Per-Tenant Authentication

Add basic HTTP authentication to the shared MLflow tracking server so each tenant gets their own login (`user-{{guid}}` / common password) and can only see their own experiment. Athena authenticates as the tenant user when logging traces.

**Extends**: `2026-05-27-mlflow-tracing-design.md` — that spec explicitly listed auth as out of scope; this spec fills the gap.

## Problem

The shared MLflow server has no authentication. All tenants share the same UI and can browse, select, and modify each other's experiments and traces. In a multi-tenant lab environment this causes confusion (wrong experiment selected) and data integrity risk (traces deleted or experiments renamed by the wrong user).

## Decisions

- **Auth method**: MLflow built-in basic HTTP auth (`--app-name basic-auth`)
- **Isolation model**: `default_permission = NO_PERMISSIONS` — users only see experiments they've been explicitly granted access to
- **Auth database**: Reuse the existing PostgreSQL instance (same database, separate tables created by MLflow auth plugin)
- **Tenant credentials**: `user-{{guid}}` with `common_admin_password` — consistent with AAP2, Kira, RocketChat credential pattern
- **Athena integration**: Tenant credentials passed via `MLFLOW_TRACKING_USERNAME` / `MLFLOW_TRACKING_PASSWORD` env vars
- **Admin credentials**: `admin` / `common_admin_password` — used by deployer for user management API calls

## Known Risks and Mitigations

### Risk 1: `--app-name basic-auth` with gunicorn

The community Helm chart forces gunicorn when `postgresql.enabled=true` (adds `--gunicorn-opts`). We were burned by `--allowed-hosts` which is uvicorn-only. However, `--app-name` modifies the WSGI app object before handing it to the server — it should work with both backends. If it fails, fall back to the `MLFLOW_APP_NAME` env var or inject the flag via `--gunicorn-opts`.

### Risk 2: `mlflow[auth]` dependency in container image

Basic auth requires the `mlflow[auth]` extra. The community chart uses `ghcr.io/mlflow/mlflow` which may or may not include it. **Must verify** before deploying. If missing, we need a custom image or an init container that installs the extra.

### Risk 3: Deployer uses external Route URL

The Ansible deployer runs remotely (RHPDS) and cannot reach internal service URLs. All MLflow REST API calls (create experiment, create user, grant permission) use the external Route URL and must include `Authorization: Basic` headers with admin credentials. Use `ansible.builtin.uri` with `force_basic_auth: true`, `url_username`, and `url_password`.

### Risk 4: PostgreSQL auth DB connection string must match PVC-baked password

Bitnami PostgreSQL bakes the password into the PVC on first boot. The auth config INI's `database_uri` must use the password that's actually in PostgreSQL, not what's in the current Helm values (these can diverge after `helm upgrade`). On cluster-b8xxn specifically, the password was manually set to `mlflow-pg` via `ALTER USER`.

### Risk 5: First-boot timing — auth DB init vs tenant deployer

After enabling auth, the cluster role's health check (`/health`) confirms MLflow is up, but auth tables may not be fully initialized. Add a verification step that hits `GET /api/2.0/mlflow/users/get?username=admin` with admin credentials after the health check. Retry until 200.

### Risk 6: Third-party cookies in showroom iframe

MLflow session cookies may not persist in the showroom iframe due to browser third-party cookie restrictions. Both domains are under `*.apps.cluster-xxx.dynamic2.redhatworkshops.io` (same eTLD+1), so SameSite=Lax cookies should work. If not, document that users can open MLflow in a new browser tab.

### Risk 7: Existing tenant loses access on upgrade

Enabling auth with `NO_PERMISSIONS` locks out existing tenants (e.g., user-994ds on cluster-b8xxn). After `helm upgrade`, re-run the tenant role for existing users to create their accounts and grant permissions.

### Risk 8: `/health` endpoint auth requirements

Verify that `/health` remains unauthenticated after enabling basic auth. If it requires auth, the cluster role's health check and Kubernetes probes will fail. Liveness/readiness probes in the Helm chart may need `httpHeaders` with Basic auth.

## Subsystem Decomposition

```
1. Cluster Role Changes (deepagents-aiops)
   └─ Enable basic auth, mount auth config, add admin verification
   
2. Tenant Role Changes (deepagents-aiops)
   └─ Create user, grant experiment permission, authenticate API calls
   └─ Depends on: (1)

3. Tenant Cleanup Changes (deepagents-aiops)
   └─ Delete user on remove_workload
   └─ Depends on: (1)

4. Athena Tenant Wiring (deepagents-aiops + athena-aiops-deep-agent)
   └─ Wire MLFLOW_TRACKING_USERNAME/PASSWORD through Helm
   └─ Depends on: (2)
```

## Cluster Role: `ocp4_workload_mlflow_cluster`

### New: Auth config ConfigMap

Create a ConfigMap with the MLflow auth configuration INI before the Helm install:

```yaml
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
    admin_username = admin
    admin_password = {{ common_admin_password }}
    authorization_function = mlflow.server.auth:authenticate_request_basic_auth
```

### Helm values changes

Add to the existing `kubernetes.core.helm` task's `values:` block:

```yaml
extraArgs:
  app-name: basic-auth

extraEnvVars:
  MLFLOW_SERVER_DISABLE_SECURITY_MIDDLEWARE: "true"   # keep — orthogonal to auth
  MLFLOW_AUTH_CONFIG_PATH: /etc/mlflow/auth_config.ini
  MLFLOW_FLASK_SERVER_SECRET_KEY: "{{ common_admin_password }}"

extraVolumes:
  - name: auth-config
    configMap:
      name: mlflow-auth-config

extraVolumeMounts:
  - name: auth-config
    mountPath: /etc/mlflow
    readOnly: true
```

### New: Admin user verification step

After the existing health check, add:

```yaml
- name: Verify MLflow auth is operational
  ansible.builtin.uri:
    url: "{{ _ocp4_workload_mlflow_cluster_url }}/api/2.0/mlflow/users/get?username=admin"
    method: GET
    force_basic_auth: true
    url_username: admin
    url_password: "{{ common_admin_password }}"
    validate_certs: false
    status_code: 200
  retries: 30
  delay: 10
  until: r_mlflow_auth is succeeded
  register: r_mlflow_auth
```

### Defaults additions

```yaml
ocp4_workload_mlflow_cluster_admin_username: admin
ocp4_workload_mlflow_cluster_admin_password: "{{ common_admin_password }}"
```

## Tenant Role: `ocp4_workload_mlflow_tenant`

### workload.yml changes

All existing API calls need Basic auth headers. Add to each `ansible.builtin.uri` task:

```yaml
force_basic_auth: true
url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
```

### New tasks (after experiment creation)

```yaml
# 1. Create tenant user
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
      - 409   # user already exists — idempotent
    validate_certs: false

# 2. Grant experiment permission
- name: Grant tenant MANAGE permission on their experiment
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/experiments/permissions/create"
    method: POST
    body_format: json
    body:
      experiment_id: "{{ r_experiment.json.experiment_id }}"
      username: "{{ ocp4_workload_mlflow_tenant_username }}"
      permission: MANAGE
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
    status_code:
      - 200
      - 409   # permission already exists
    validate_certs: false
```

### Defaults additions

```yaml
ocp4_workload_mlflow_tenant_username: "user-{{ guid }}"
ocp4_workload_mlflow_tenant_password: "{{ common_admin_password }}"
ocp4_workload_mlflow_tenant_admin_username: admin
ocp4_workload_mlflow_tenant_admin_password: "{{ common_admin_password }}"
```

### Save connection info

Add MLflow credentials to `agnosticd_user_info` so downstream roles (Athena tenant) can use them:

```yaml
- name: Save MLflow tenant info
  agnosticd.core.agnosticd_user_info:
    data:
      mlflow_username: "{{ ocp4_workload_mlflow_tenant_username }}"
      mlflow_password: "{{ ocp4_workload_mlflow_tenant_password }}"
```

## Tenant Cleanup: `remove_workload.yml`

Add after the existing experiment soft-delete:

```yaml
- name: Delete MLflow tenant user
  ansible.builtin.uri:
    url: "{{ ocp4_workload_mlflow_tenant_tracking_uri }}/api/2.0/mlflow/users/delete?username={{ ocp4_workload_mlflow_tenant_username | urlencode }}"
    method: DELETE
    force_basic_auth: true
    url_username: "{{ ocp4_workload_mlflow_tenant_admin_username }}"
    url_password: "{{ ocp4_workload_mlflow_tenant_admin_password }}"
    status_code:
      - 200
      - 404   # user already deleted
    validate_certs: false
  ignore_errors: true
```

The existing experiment lookup and delete tasks also need the `force_basic_auth` / `url_username` / `url_password` parameters added.

## Athena Tenant Wiring

### Athena Helm chart (`deploy/helm/athena/`)

**`values.yaml`** — add under existing `mlflow:` section:

```yaml
mlflow:
  trackingUri: ""
  experimentName: ""
  username: ""      # NEW
  password: ""      # NEW
```

**`templates/deployment.yaml`** — add inside the MLflow conditional block:

```yaml
{{- if .Values.mlflow.username }}
- name: MLFLOW_TRACKING_USERNAME
  value: {{ .Values.mlflow.username | quote }}
{{- end }}
{{- if .Values.mlflow.password }}
- name: MLFLOW_TRACKING_PASSWORD
  value: {{ .Values.mlflow.password | quote }}
{{- end }}
```

### Athena tenant deployer (`ocp4_workload_athena_tenant`)

Add MLflow credential defaults and wire through to Helm values:

```yaml
# defaults/main.yml
ocp4_workload_athena_tenant_mlflow_username: ""
ocp4_workload_athena_tenant_mlflow_password: ""
```

Wire in the Helm values block in `workload.yml`:

```yaml
mlflow:
  trackingUri: "{{ ocp4_workload_athena_tenant_mlflow_tracking_uri }}"
  experimentName: "{{ ocp4_workload_athena_tenant_mlflow_experiment_name }}"
  username: "{{ ocp4_workload_athena_tenant_mlflow_username }}"
  password: "{{ ocp4_workload_athena_tenant_mlflow_password }}"
```

### agnosticv `dev.yaml`

Add MLflow credentials alongside the existing tracking URI:

```yaml
ocp4_workload_athena_tenant_mlflow_tracking_uri: "http://mlflow.mlflow.svc.cluster.local"
ocp4_workload_athena_tenant_mlflow_experiment_name: "{{ ocp4_workload_username }}-agentic"
ocp4_workload_athena_tenant_mlflow_username: "user-{{ guid }}"
ocp4_workload_athena_tenant_mlflow_password: "{{ common_admin_password }}"
```

Note: Athena uses the **internal** service URL (no auth middleware issue inside cluster). The MLflow Python client authenticates via the `MLFLOW_TRACKING_USERNAME` / `MLFLOW_TRACKING_PASSWORD` env vars — no URL change needed.

## Athena Code Changes

### `athena/app.py` — no changes needed

The MLflow Python client automatically picks up `MLFLOW_TRACKING_USERNAME` and `MLFLOW_TRACKING_PASSWORD` from environment variables. The existing `mlflow.set_tracking_uri()` / `mlflow.set_experiment()` / `mlflow.langchain.autolog()` code works unchanged.

### `athena/config.py` — add optional settings

```python
mlflow_tracking_username: str | None = None
mlflow_tracking_password: str | None = None
```

These are for documentation/validation only — the MLflow client reads them directly from env vars, not from our Settings object.

## Files Changed

### Deployer (`deepagents-aiops`)

| File | Change |
|------|--------|
| `roles/ocp4_workload_mlflow_cluster/tasks/workload.yml` | Add ConfigMap, extraArgs, extraVolumes, admin verification |
| `roles/ocp4_workload_mlflow_cluster/defaults/main.yml` | Add admin username/password defaults |
| `roles/ocp4_workload_mlflow_tenant/tasks/workload.yml` | Add auth headers, user creation, permission grant |
| `roles/ocp4_workload_mlflow_tenant/tasks/remove_workload.yml` | Add auth headers, user deletion |
| `roles/ocp4_workload_mlflow_tenant/defaults/main.yml` | Add tenant username/password/admin defaults |
| `roles/ocp4_workload_athena_tenant/defaults/main.yml` | Add MLflow username/password defaults |
| `roles/ocp4_workload_athena_tenant/tasks/workload.yml` | Wire MLflow credentials to Helm |

### Athena Helm chart (`deploy/helm/athena/`)

| File | Change |
|------|--------|
| `values.yaml` | Add `mlflow.username`, `mlflow.password` |
| `templates/deployment.yaml` | Wire `MLFLOW_TRACKING_USERNAME`, `MLFLOW_TRACKING_PASSWORD` |

### Athena code (`athena-aiops-deep-agent`)

| File | Change |
|------|--------|
| `athena/config.py` | Add optional `mlflow_tracking_username`, `mlflow_tracking_password` |

### agnosticv (branch: `feat/kira-frontend-0.11.1`)

| File | Change |
|------|--------|
| `summit-2026/lb2645-agentic-devops-tenant/dev.yaml` | Add MLflow username/password vars |

## Testing

### Verification steps after deploy

1. `helm upgrade` completes without pod crash (validates `--app-name basic-auth` works with gunicorn)
2. MLflow UI shows login prompt at the Route URL
3. Admin can log in with `admin` / `common_admin_password`
4. Tenant user can log in with `user-{{guid}}` / `common_admin_password`
5. Tenant user sees only their own experiment
6. Admin sees all experiments
7. Athena pod starts normally with MLflow credentials
8. Trigger a failed job → verify trace appears in MLflow under the tenant's experiment
9. Showroom MLflow tab loads login prompt, user can authenticate

### Failure modes to test

- MLflow pod restart → auth database persists (PostgreSQL-backed)
- Tenant remove → user and permissions deleted, experiment soft-deleted
- Wrong credentials in Athena → traces fail silently, pipeline continues
- MLflow unreachable → Athena starts normally (existing try/except guard)

## Deployment Order

1. Update cluster role (enables auth on shared server)
2. `helm upgrade` the MLflow release on cluster-b8xxn
3. Re-run tenant role for existing tenants (creates their user accounts)
4. Update and rebuild Athena image (adds config.py fields) — optional, env vars work without code changes
5. Update agnosticv dev.yaml with credentials
6. Redeploy Athena tenant with new env vars
