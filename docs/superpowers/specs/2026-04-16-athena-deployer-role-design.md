# Athena Deployer Role Design

**Date:** 2026-04-16
**Status:** Approved
**Scope:** Ansible collection role `ocp4_workload_athena_tenant` in `rhpds.deepagents_aiops`

## Purpose

Deploy the Athena AIOps service into a per-tenant namespace via AgnosticV, fully wired to Kira, Rocket.Chat, AAP2, and MaaS. The role runs as part of the tenant catalog item workload chain, after all dependency services are provisioned.

## Position in Tenant CI Workload Order

```yaml
workloads:
  - agnosticd.namespaced_workloads.ocp4_workload_tenant_keycloak_user
  - agnosticd.namespaced_workloads.ocp4_workload_tenant_namespace
  - rhpds.litellm_virtual_keys.ocp4_workload_litellm_virtual_keys
  - agnosticd.namespaced_workloads.ocp4_workload_tenant_gitea_user
  - rhpds.deepagents_aiops.ocp4_workload_rhel_vm_tenant
  - rhpds.deepagents_aiops.ocp4_workload_aap2_tenant_config
  - rhpds.deepagents_aiops.ocp4_workload_kira_tenant
  - rhpds.deepagents_aiops.ocp4_workload_rocketchat_tenant
  - rhpds.deepagents_aiops.ocp4_workload_athena_tenant      # <-- NEW
  - agnosticd.showroom.ocp4_workload_showroom
```

Athena runs after all dependency services (Kira, Rocket.Chat, AAP2, MaaS) are provisioned. It runs before Showroom so connection info is available for the lab UI.

## Deployment Pattern

Clone-and-Helm, matching the `ocp4_workload_kira_tenant` role pattern exactly:

1. Clone the Athena repo to get the Helm chart from `deploy/helm/athena/`
2. Template Helm values with collected credentials
3. Deploy via `kubernetes.core.helm`
4. Post-deployment configuration (webhook registration)

## Task Flow

### Step 1: Read AAP2 Admin Credentials

Read the `aap-admin-credentials` Secret from the `aap` namespace using `kubernetes.core.k8s_info`. Same pattern as `ocp4_workload_aap2_tenant_config`. Extract and decode `url`, `username`, `password` fields. Assert the secret exists (fail fast if cluster CI didn't provision AAP2).

### Step 2: Discover Kira Routes

Look up two Routes in the tenant namespace via `k8s_info`:

- **Kira API route** — label selector: `app.kubernetes.io/component=api,app.kubernetes.io/instance=kira`. Provides `KIRA_URL` (as `https://` + hostname).
- **Kira Frontend route** — label selector: `app.kubernetes.io/component=frontend,app.kubernetes.io/instance=kira`. Provides `KIRA_FRONTEND_URL` for ticket links in notifications.

### Step 3: Discover Rocket.Chat Route

Look up the Rocket.Chat Route in the tenant namespace via `k8s_info`. Provides `ROCKETCHAT_URL`.

### Step 4: Create Rocket.Chat Bot User

Using the RC admin credentials (known from catalog variables):

1. **Login as RC admin** — `POST /api/v1/login` with admin username/password. Extract `authToken` and `userId` from response.
2. **Create `aiops` bot user** — `POST /api/v1/users.create` with:
   - `username: aiops`
   - `name: Athena AIOps`
   - `password: <from variable>`
   - `roles: ["bot"]`
   - `verified: true`
   - Handle 400 (already exists) as success.

### Step 5: Login as Bot User

`POST /api/v1/login` as the `aiops` user. Extract `authToken` and `userId` — these become `ROCKETCHAT_API_AUTH_TOKEN` and `ROCKETCHAT_API_USER_ID` for Athena.

### Step 6: Clone Athena Repo and Template Helm Values

Clone the Athena repo (`ansible.builtin.git`) to `/tmp/athena-helm`. Create `/tmp/athena-helm-values.yaml` from a Jinja2 template (`templates/helm-values.yaml.j2`) mapping all collected credentials and configuration to Helm values.

### Step 7: Helm Deploy

```yaml
kubernetes.core.helm:
  name: athena
  chart_ref: /tmp/athena-helm/deploy/helm/athena
  release_namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
  values_files:
    - /tmp/athena-helm-values.yaml
  state: present
  wait: false
```

### Step 8: Wait for Readiness

Poll the Athena deployment for ready replicas using `k8s_info` with retries/delay. The pod exposes `/readyz` which returns 200 only after startup completes.

### Step 9: Register AAP2 Webhook

After Athena is running, look up the Athena Route URL. Then register the webhook using AAP2 controller modules:

1. **Create notification template** — `ansible.controller.notification_template` of type `webhook`, pointing to `https://<athena-route>/api/v1/webhook/aap2`.
2. **Attach to organization** — associate the notification template with the tenant org so failed jobs trigger the webhook.

Use the AAP2 admin credentials obtained in Step 1.

### Step 10: Save Connection Info

```yaml
agnosticd.core.agnosticd_user_info:
  data:
    athena_url: "https://{{ _athena_route_host }}"
    athena_webhook_url: "https://{{ _athena_route_host }}/api/v1/webhook/aap2"
```

### Step 11: Cleanup

Remove temporary files:
- `/tmp/athena-helm` (cloned repo)
- `/tmp/athena-helm-values.yaml` (templated values)

## Credential Flow

| Credential | Source | How Obtained |
|---|---|---|
| AAP2 admin URL/user/pass | `aap-admin-credentials` Secret in `aap` ns | `k8s_info` + b64decode |
| AAP2 organization | Catalog variable | `org-{{ guid }}` |
| Kira API URL | Route in tenant namespace | `k8s_info` Route lookup |
| Kira Frontend URL | Route in tenant namespace | `k8s_info` Route lookup |
| Kira API key | Catalog variable | Same `common_password` used by kira_tenant |
| Rocket.Chat URL | Route in tenant namespace | `k8s_info` Route lookup |
| RC auth token | RC API login as `aiops` | POST `/api/v1/login` |
| RC user ID | RC API login as `aiops` | POST `/api/v1/login` |
| MaaS API base URL | `litellm_api_endpoint` | Passed from catalog (litellm_virtual_keys workload) |
| MaaS API key | `litellm_virtual_key` | Passed from catalog (litellm_virtual_keys workload) |

## Variables (defaults/main.yml)

```yaml
# Image
ocp4_workload_athena_tenant_image: quay.io/tonykay/athena-aiops
ocp4_workload_athena_tenant_tag: latest

# Helm chart source
ocp4_workload_athena_tenant_helm_repo: https://github.com/tonykay/athena-aiops-deep-agent.git
ocp4_workload_athena_tenant_helm_repo_ref: main
ocp4_workload_athena_tenant_helm_chart_path: deploy/helm/athena

# Namespace
ocp4_workload_athena_tenant_namespace: "user-{{ guid }}-agentic"

# Release
ocp4_workload_athena_tenant_release_name: athena

# AAP2 admin (for webhook registration)
ocp4_workload_athena_tenant_aap2_admin_secret: aap-admin-credentials
ocp4_workload_athena_tenant_aap2_admin_namespace: aap
ocp4_workload_athena_tenant_aap2_organization: "org-{{ guid }}"
ocp4_workload_athena_tenant_aap2_validate_certs: false

# Kira
ocp4_workload_athena_tenant_kira_api_key: "{{ common_password | default('dev-api-key') }}"

# Rocket.Chat
ocp4_workload_athena_tenant_rocketchat_admin_username: admin
ocp4_workload_athena_tenant_rocketchat_admin_password: "{{ common_password | default('admin') }}"
ocp4_workload_athena_tenant_rocketchat_bot_username: aiops
ocp4_workload_athena_tenant_rocketchat_bot_password: "{{ common_password | default('aiops') }}"
ocp4_workload_athena_tenant_rocketchat_channel: support

# MaaS / LLM
ocp4_workload_athena_tenant_maas_api_base: "{{ litellm_api_endpoint | default('') }}"
ocp4_workload_athena_tenant_maas_api_key: "{{ litellm_virtual_key | default('') }}"

# Agent models
ocp4_workload_athena_tenant_ops_manager_model: "openai/claude-sonnet-4-6"
ocp4_workload_athena_tenant_specialist_model: "openai/claude-sonnet-4-6"
ocp4_workload_athena_tenant_reviewer_model: "openai/claude-3-5-haiku"

# Retry configuration
ocp4_workload_athena_tenant_deploy_retries: 60
ocp4_workload_athena_tenant_deploy_retry_delay: 10
```

## Helm Values Template

The `templates/helm-values.yaml.j2` maps role variables to Athena's Helm chart values:

```yaml
image:
  repository: {{ ocp4_workload_athena_tenant_image }}
  tag: {{ ocp4_workload_athena_tenant_tag }}
  pullPolicy: Always

aap2:
  url: {{ _ocp4_workload_athena_tenant_aap2_url }}
  username: {{ _ocp4_workload_athena_tenant_aap2_username }}
  password: {{ _ocp4_workload_athena_tenant_aap2_password }}
  organization: {{ ocp4_workload_athena_tenant_aap2_organization }}

kira:
  url: https://{{ _ocp4_workload_athena_tenant_kira_api_host }}
  apiKey: {{ ocp4_workload_athena_tenant_kira_api_key }}
  frontendUrl: https://{{ _ocp4_workload_athena_tenant_kira_frontend_host }}

rocketchat:
  url: https://{{ _ocp4_workload_athena_tenant_rocketchat_host }}
  apiAuthToken: {{ _ocp4_workload_athena_tenant_rocketchat_auth_token }}
  apiUserId: {{ _ocp4_workload_athena_tenant_rocketchat_user_id }}
  channel: {{ ocp4_workload_athena_tenant_rocketchat_channel }}

maas:
  apiBaseUrl: {{ ocp4_workload_athena_tenant_maas_api_base }}
  virtualKey: {{ ocp4_workload_athena_tenant_maas_api_key }}

agentConfig:
  opsManagerModel: {{ ocp4_workload_athena_tenant_ops_manager_model }}
  specialistModel: {{ ocp4_workload_athena_tenant_specialist_model }}
  reviewerModel: {{ ocp4_workload_athena_tenant_reviewer_model }}

skills:
  persistence:
    enabled: false

route:
  enabled: true
```

## Removal (remove_workload.yml)

1. Remove AAP2 notification template (query + DELETE via controller API)
2. Remove Helm release (`kubernetes.core.helm` with `state: absent`)
3. Delete the `aiops` RC bot user (POST `/api/v1/users.delete`)
4. Cleanup temp files

## File Structure

```
roles/ocp4_workload_athena_tenant/
  defaults/main.yml
  tasks/
    main.yml              # ACTION dispatch (provision/destroy)
    workload.yml          # Provision logic (Steps 1-11)
    remove_workload.yml   # Cleanup logic
  templates/
    helm-values.yaml.j2   # Helm values template
```

## Design Decisions

**No Skills PVC:** Skills are baked into the container image. For a summit lab with pre-built images, this avoids PVC complexity. If skills need updating, rebuild the image.

**Bot user over admin:** Athena posts to Rocket.Chat as `aiops` (bot role) rather than admin. This gives clear attribution in the `#support` channel and follows least-privilege.

**Role registers webhook, not Athena startup:** Avoids the chicken-and-egg of Athena needing its own Route URL before it's deployed. The Ansible role has AAP2 admin creds and can register the notification template after deployment, which is more reliable.

**Dynamic route discovery:** Kira and Rocket.Chat URLs are discovered via Route lookups rather than passed as catalog variables. This avoids coupling the catalog item to internal route naming and is resilient to hostname changes.

**Session-scoped RC auth token:** The bot's auth token is obtained via login and passed to Athena. For a summit lab (hours to days), token expiry is not a concern. For production use, personal access tokens would be preferable.
