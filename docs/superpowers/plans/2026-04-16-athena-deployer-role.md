# Athena Deployer Role Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `ocp4_workload_athena_tenant` Ansible role in the `rhpds.deepagents_aiops` collection that deploys Athena AIOps into per-tenant namespaces, wired to Kira, Rocket.Chat, AAP2, and MaaS.

**Architecture:** Helm-based deployment following the existing `ocp4_workload_kira_tenant` pattern. The role discovers dependency service URLs via Route lookups, creates a Rocket.Chat bot user for notifications, deploys Athena via its Helm chart, and registers the AAP2 webhook notification template with the correct external URL.

**Tech Stack:** Ansible, `kubernetes.core` collection, `ansible.controller` collection, Helm 3, OpenShift Routes

**Spec:** `docs/superpowers/specs/2026-04-16-athena-deployer-role-design.md`

**Collection repo:** `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/`

---

## File Structure

```
roles/ocp4_workload_athena_tenant/
  defaults/main.yml           — All role variables with defaults
  tasks/
    main.yml                  — ACTION dispatch (provision vs. destroy)
    workload.yml              — Provision: discover creds, create RC bot, helm deploy, register webhook
    remove_workload.yml       — Cleanup: remove webhook, helm, RC bot user
  templates/
    helm-values.yaml.j2       — Maps role variables to Athena Helm chart values
```

---

### Task 1: Create Role Skeleton

**Files:**
- Create: `roles/ocp4_workload_athena_tenant/defaults/main.yml`
- Create: `roles/ocp4_workload_athena_tenant/tasks/main.yml`

- [ ] **Step 1: Create defaults/main.yml**

```yaml
---
# ===================================================================
# Role: ocp4_workload_athena_tenant
# Deploys Athena AIOps service per tenant via Helm.
# ===================================================================

# Container image
ocp4_workload_athena_tenant_image: quay.io/tonykay/athena-aiops
ocp4_workload_athena_tenant_tag: latest

# Helm chart source
ocp4_workload_athena_tenant_helm_repo: https://github.com/tonykay/athena-aiops-deep-agent.git
ocp4_workload_athena_tenant_helm_repo_ref: main
ocp4_workload_athena_tenant_helm_chart_path: deploy/helm/athena

# Target namespace
ocp4_workload_athena_tenant_namespace: "user-{{ guid }}-agentic"

# Helm release name
ocp4_workload_athena_tenant_release_name: athena

# AAP2 admin credentials (read from cluster secret for webhook registration)
ocp4_workload_athena_tenant_aap2_admin_secret: aap-admin-credentials
ocp4_workload_athena_tenant_aap2_admin_namespace: aap
ocp4_workload_athena_tenant_aap2_organization: "org-{{ guid }}"
ocp4_workload_athena_tenant_aap2_validate_certs: false

# Kira API key (must match the key used by ocp4_workload_kira_tenant)
ocp4_workload_athena_tenant_kira_api_key: "{{ common_password | default('dev-api-key') }}"

# Rocket.Chat admin credentials (must match ocp4_workload_rocketchat_tenant)
ocp4_workload_athena_tenant_rocketchat_admin_username: admin
ocp4_workload_athena_tenant_rocketchat_admin_password: "{{ common_password | default('admin') }}"

# Rocket.Chat bot user for Athena notifications
ocp4_workload_athena_tenant_rocketchat_bot_username: aiops
ocp4_workload_athena_tenant_rocketchat_bot_password: "{{ common_password | default('aiops') }}"
ocp4_workload_athena_tenant_rocketchat_channel: support

# MaaS / LLM gateway
ocp4_workload_athena_tenant_maas_api_base: "{{ litellm_api_endpoint | default('') }}"
ocp4_workload_athena_tenant_maas_api_key: "{{ litellm_virtual_key | default('') }}"

# Agent model configuration
ocp4_workload_athena_tenant_ops_manager_model: "openai/claude-sonnet-4-6"
ocp4_workload_athena_tenant_specialist_model: "openai/claude-sonnet-4-6"
ocp4_workload_athena_tenant_reviewer_model: "openai/claude-3-5-haiku"

# Retry configuration
ocp4_workload_athena_tenant_deploy_retries: 60
ocp4_workload_athena_tenant_deploy_retry_delay: 10
ocp4_workload_athena_tenant_api_retries: 10
ocp4_workload_athena_tenant_api_retry_delay: 5
```

- [ ] **Step 2: Create tasks/main.yml**

```yaml
---
# --------------------------------------------------
# Do not modify this file
# --------------------------------------------------
- name: Running workload provision tasks
  when: ACTION == "provision"
  ansible.builtin.include_tasks: workload.yml

- name: Running workload removal tasks
  when: ACTION == "destroy"
  ansible.builtin.include_tasks: remove_workload.yml
```

- [ ] **Step 3: Validate YAML syntax**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && python -c "import yaml; yaml.safe_load(open('roles/ocp4_workload_athena_tenant/defaults/main.yml')); yaml.safe_load(open('roles/ocp4_workload_athena_tenant/tasks/main.yml')); print('YAML OK')"`

Expected: `YAML OK`

- [ ] **Step 4: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/defaults/main.yml roles/ocp4_workload_athena_tenant/tasks/main.yml
git commit -m "feat(athena): add role skeleton with defaults and task dispatch"
```

---

### Task 2: Create Helm Values Template

**Files:**
- Create: `roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2`

This template maps role variables to the Athena Helm chart's `values.yaml` structure. Sensitive values (passwords, API keys, auth tokens) go through Helm's Secret template. Non-sensitive values go through the Deployment template as plain env vars.

Reference: Athena's Helm chart values structure is at `deploy/helm/athena/values.yaml` in the athena-aiops-deep-agent repo.

- [ ] **Step 1: Create templates/helm-values.yaml.j2**

```yaml
image:
  repository: {{ ocp4_workload_athena_tenant_image }}
  tag: "{{ ocp4_workload_athena_tenant_tag }}"
  pullPolicy: Always

aap2:
  url: "{{ _ocp4_workload_athena_tenant_aap2_url }}"
  username: "{{ _ocp4_workload_athena_tenant_aap2_username }}"
  password: "{{ _ocp4_workload_athena_tenant_aap2_password }}"
  organization: "{{ ocp4_workload_athena_tenant_aap2_organization }}"

kira:
  url: "https://{{ _ocp4_workload_athena_tenant_kira_api_host }}"
  apiKey: "{{ ocp4_workload_athena_tenant_kira_api_key }}"
  frontendUrl: "https://{{ _ocp4_workload_athena_tenant_kira_frontend_host }}"

rocketchat:
  url: "https://{{ _ocp4_workload_athena_tenant_rocketchat_host }}"
  apiAuthToken: "{{ _ocp4_workload_athena_tenant_rocketchat_auth_token }}"
  apiUserId: "{{ _ocp4_workload_athena_tenant_rocketchat_user_id }}"
  channel: "{{ ocp4_workload_athena_tenant_rocketchat_channel }}"

maas:
  apiBaseUrl: "{{ ocp4_workload_athena_tenant_maas_api_base }}"
  virtualKey: "{{ ocp4_workload_athena_tenant_maas_api_key }}"

tavily:
  apiKey: ""

agentConfig:
  opsManagerModel: "{{ ocp4_workload_athena_tenant_ops_manager_model }}"
  specialistModel: "{{ ocp4_workload_athena_tenant_specialist_model }}"
  reviewerModel: "{{ ocp4_workload_athena_tenant_reviewer_model }}"
  agentsMd: ""
  subagentsYaml: ""

skills:
  persistence:
    enabled: false

route:
  enabled: true

service:
  port: 8080
  type: ClusterIP

resources:
  requests:
    cpu: 100m
    memory: 256Mi
  limits:
    cpu: 500m
    memory: 512Mi
```

- [ ] **Step 2: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2
git commit -m "feat(athena): add Helm values template"
```

---

### Task 3: Write Credential Discovery Tasks

**Files:**
- Create: `roles/ocp4_workload_athena_tenant/tasks/workload.yml` (first section)

This task creates the beginning of `workload.yml` with three discovery steps:
1. Read AAP2 admin credentials from the cluster secret in the `aap` namespace
2. Look up Kira API and Frontend routes in the tenant namespace
3. Look up Rocket.Chat route in the tenant namespace

These set internal `_` prefixed facts used by later tasks and the Helm values template.

Pattern reference: `roles/ocp4_workload_aap2_tenant_config/tasks/workload.yml` lines 1-35 for the AAP2 secret reading pattern.

- [ ] **Step 1: Create tasks/workload.yml with credential discovery**

```yaml
---
# ===================================================================
# Deploy Athena AIOps service per tenant via Helm
# ===================================================================

# -------------------------------------------------------------------
# 0. Grant anyuid SCC to default service account
# -------------------------------------------------------------------
- name: Grant anyuid SCC for Athena pods
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: rbac.authorization.k8s.io/v1
      kind: RoleBinding
      metadata:
        name: athena-anyuid
        namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
      roleRef:
        apiGroup: rbac.authorization.k8s.io
        kind: ClusterRole
        name: system:openshift:scc:anyuid
      subjects:
        - kind: ServiceAccount
          name: default
          namespace: "{{ ocp4_workload_athena_tenant_namespace }}"

# -------------------------------------------------------------------
# 1. Read AAP2 admin credentials from cluster secret
# -------------------------------------------------------------------
- name: Get AAP admin credentials secret
  kubernetes.core.k8s_info:
    api_version: v1
    kind: Secret
    name: "{{ ocp4_workload_athena_tenant_aap2_admin_secret }}"
    namespace: "{{ ocp4_workload_athena_tenant_aap2_admin_namespace }}"
  register: r_aap_admin_secret

- name: Assert AAP admin credentials secret exists
  ansible.builtin.assert:
    that:
      - r_aap_admin_secret.resources | length > 0
    fail_msg: >-
      AAP admin credentials secret '{{ ocp4_workload_athena_tenant_aap2_admin_secret }}'
      not found in namespace '{{ ocp4_workload_athena_tenant_aap2_admin_namespace }}'.
      Ensure ocp4_workload_ansible_automation_platform ran with
      ocp4_workload_ansible_automation_platform_save_admin_credentials: true.

- name: Extract AAP admin credentials from secret
  ansible.builtin.set_fact:
    _ocp4_workload_athena_tenant_aap2_url: >-
      {{ r_aap_admin_secret.resources[0].data.url | b64decode }}
    _ocp4_workload_athena_tenant_aap2_username: >-
      {{ r_aap_admin_secret.resources[0].data.username | b64decode }}
    _ocp4_workload_athena_tenant_aap2_password: >-
      {{ r_aap_admin_secret.resources[0].data.password | b64decode }}
  no_log: true

# -------------------------------------------------------------------
# 2. Discover Kira routes in tenant namespace
# -------------------------------------------------------------------
- name: Get Kira API route
  kubernetes.core.k8s_info:
    api_version: route.openshift.io/v1
    kind: Route
    namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
    label_selectors:
      - "app.kubernetes.io/component=api"
      - "app.kubernetes.io/instance=kira"
  register: r_kira_api_route

- name: Assert Kira API route exists
  ansible.builtin.assert:
    that:
      - r_kira_api_route.resources | length > 0
    fail_msg: >-
      Kira API route not found in namespace '{{ ocp4_workload_athena_tenant_namespace }}'.
      Ensure ocp4_workload_kira_tenant ran before this role.

- name: Set Kira API host fact
  ansible.builtin.set_fact:
    _ocp4_workload_athena_tenant_kira_api_host: >-
      {{ r_kira_api_route.resources[0].spec.host }}

- name: Get Kira frontend route
  kubernetes.core.k8s_info:
    api_version: route.openshift.io/v1
    kind: Route
    namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
    label_selectors:
      - "app.kubernetes.io/component=frontend"
      - "app.kubernetes.io/instance=kira"
  register: r_kira_frontend_route

- name: Assert Kira frontend route exists
  ansible.builtin.assert:
    that:
      - r_kira_frontend_route.resources | length > 0
    fail_msg: >-
      Kira frontend route not found in namespace '{{ ocp4_workload_athena_tenant_namespace }}'.
      Ensure ocp4_workload_kira_tenant ran before this role.

- name: Set Kira frontend host fact
  ansible.builtin.set_fact:
    _ocp4_workload_athena_tenant_kira_frontend_host: >-
      {{ r_kira_frontend_route.resources[0].spec.host }}

# -------------------------------------------------------------------
# 3. Discover Rocket.Chat route in tenant namespace
# -------------------------------------------------------------------
- name: Get Rocket.Chat route
  kubernetes.core.k8s_info:
    api_version: route.openshift.io/v1
    kind: Route
    name: rocketchat
    namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
  register: r_rocketchat_route

- name: Assert Rocket.Chat route exists
  ansible.builtin.assert:
    that:
      - r_rocketchat_route.resources | length > 0
    fail_msg: >-
      Rocket.Chat route 'rocketchat' not found in namespace
      '{{ ocp4_workload_athena_tenant_namespace }}'.
      Ensure ocp4_workload_rocketchat_tenant ran before this role.

- name: Set Rocket.Chat host fact
  ansible.builtin.set_fact:
    _ocp4_workload_athena_tenant_rocketchat_host: >-
      {{ r_rocketchat_route.resources[0].spec.host }}
```

- [ ] **Step 2: Validate YAML syntax**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && python -c "import yaml; yaml.safe_load(open('roles/ocp4_workload_athena_tenant/tasks/workload.yml')); print('YAML OK')"`

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/tasks/workload.yml
git commit -m "feat(athena): add credential discovery tasks (AAP2, Kira, RC routes)"
```

---

### Task 4: Add Rocket.Chat Bot User Creation Tasks

**Files:**
- Modify: `roles/ocp4_workload_athena_tenant/tasks/workload.yml` (append)

Append three steps to `workload.yml`:
1. Login as RC admin to get auth credentials
2. Create the `aiops` bot user
3. Login as the bot user to get its auth token and user ID

Pattern reference: `roles/ocp4_workload_rocketchat_tenant/tasks/workload.yml` sections 6-7.

- [ ] **Step 1: Append RC bot user tasks to workload.yml**

Append the following to the end of `roles/ocp4_workload_athena_tenant/tasks/workload.yml`:

```yaml

# -------------------------------------------------------------------
# 4. Create Rocket.Chat bot user for Athena notifications
# -------------------------------------------------------------------
- name: Login to Rocket.Chat as admin
  ansible.builtin.uri:
    url: "https://{{ _ocp4_workload_athena_tenant_rocketchat_host }}/api/v1/login"
    method: POST
    body_format: json
    body:
      user: "{{ ocp4_workload_athena_tenant_rocketchat_admin_username }}"
      password: "{{ ocp4_workload_athena_tenant_rocketchat_admin_password }}"
    status_code: 200
    validate_certs: false
  register: r_rc_admin_login
  retries: "{{ ocp4_workload_athena_tenant_api_retries }}"
  delay: "{{ ocp4_workload_athena_tenant_api_retry_delay }}"
  until: r_rc_admin_login is succeeded
  no_log: true

- name: Set RC admin auth facts
  ansible.builtin.set_fact:
    _ocp4_workload_athena_tenant_rc_admin_auth_token: >-
      {{ r_rc_admin_login.json.data.authToken }}
    _ocp4_workload_athena_tenant_rc_admin_user_id: >-
      {{ r_rc_admin_login.json.data.userId }}
  no_log: true

- name: Create aiops bot user in Rocket.Chat
  ansible.builtin.uri:
    url: "https://{{ _ocp4_workload_athena_tenant_rocketchat_host }}/api/v1/users.create"
    method: POST
    headers:
      X-Auth-Token: "{{ _ocp4_workload_athena_tenant_rc_admin_auth_token }}"
      X-User-Id: "{{ _ocp4_workload_athena_tenant_rc_admin_user_id }}"
    body_format: json
    body:
      username: "{{ ocp4_workload_athena_tenant_rocketchat_bot_username }}"
      email: "{{ ocp4_workload_athena_tenant_rocketchat_bot_username }}@example.com"
      password: "{{ ocp4_workload_athena_tenant_rocketchat_bot_password }}"
      name: Athena AIOps
      roles:
        - bot
      verified: true
    status_code:
      - 200
      - 400
    validate_certs: false
  register: r_rc_bot_user
  changed_when: r_rc_bot_user.status == 200
  no_log: true

# -------------------------------------------------------------------
# 5. Login as bot user to get auth token for Athena
# -------------------------------------------------------------------
- name: Login to Rocket.Chat as aiops bot
  ansible.builtin.uri:
    url: "https://{{ _ocp4_workload_athena_tenant_rocketchat_host }}/api/v1/login"
    method: POST
    body_format: json
    body:
      user: "{{ ocp4_workload_athena_tenant_rocketchat_bot_username }}"
      password: "{{ ocp4_workload_athena_tenant_rocketchat_bot_password }}"
    status_code: 200
    validate_certs: false
  register: r_rc_bot_login
  retries: "{{ ocp4_workload_athena_tenant_api_retries }}"
  delay: "{{ ocp4_workload_athena_tenant_api_retry_delay }}"
  until: r_rc_bot_login is succeeded
  no_log: true

- name: Set bot auth facts for Helm values
  ansible.builtin.set_fact:
    _ocp4_workload_athena_tenant_rocketchat_auth_token: >-
      {{ r_rc_bot_login.json.data.authToken }}
    _ocp4_workload_athena_tenant_rocketchat_user_id: >-
      {{ r_rc_bot_login.json.data.userId }}
  no_log: true
```

- [ ] **Step 2: Validate YAML syntax**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && python -c "import yaml; yaml.safe_load(open('roles/ocp4_workload_athena_tenant/tasks/workload.yml')); print('YAML OK')"`

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/tasks/workload.yml
git commit -m "feat(athena): add Rocket.Chat bot user creation tasks"
```

---

### Task 5: Add Helm Deployment and Readiness Tasks

**Files:**
- Modify: `roles/ocp4_workload_athena_tenant/tasks/workload.yml` (append)

Append three steps:
1. Clone the Athena repo to get the Helm chart
2. Template the Helm values file
3. Deploy via Helm
4. Wait for the Deployment to have ready replicas

Pattern reference: `roles/ocp4_workload_kira_tenant/tasks/workload.yml` sections 1-5.

Note: Athena's Helm chart does NOT have a `namespace.yaml` template, so no patching is needed (unlike Kira).

Note: On startup, Athena will use fallback URL `http://athena:8080` for webhook registration since `ATHENA_BASE_URL` is not set. The registration API call to AAP2 will succeed (it just creates a database record), so `readyz` will return 200. The role will update the webhook URL to the correct external Route URL in Task 6.

- [ ] **Step 1: Append Helm deployment tasks to workload.yml**

Append the following to the end of `roles/ocp4_workload_athena_tenant/tasks/workload.yml`:

```yaml

# -------------------------------------------------------------------
# 6. Clone Athena repo for Helm chart
# -------------------------------------------------------------------
- name: Clone Athena repository
  ansible.builtin.git:
    repo: "{{ ocp4_workload_athena_tenant_helm_repo }}"
    dest: /tmp/athena-helm
    version: "{{ ocp4_workload_athena_tenant_helm_repo_ref }}"
    force: true

# -------------------------------------------------------------------
# 7. Generate Helm values and deploy
# -------------------------------------------------------------------
- name: Template Helm values file
  ansible.builtin.template:
    src: helm-values.yaml.j2
    dest: /tmp/athena-helm-values.yaml
    mode: "0644"

- name: Deploy Athena via Helm
  kubernetes.core.helm:
    name: "{{ ocp4_workload_athena_tenant_release_name }}"
    chart_ref: "/tmp/athena-helm/{{ ocp4_workload_athena_tenant_helm_chart_path }}"
    release_namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
    values_files:
      - /tmp/athena-helm-values.yaml
    state: present
    wait: false

# -------------------------------------------------------------------
# 8. Wait for Athena to be ready
# -------------------------------------------------------------------
- name: Wait for Athena deployment to be available
  kubernetes.core.k8s_info:
    api_version: apps/v1
    kind: Deployment
    name: "{{ ocp4_workload_athena_tenant_release_name }}"
    namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
  register: r_athena_deploy
  retries: "{{ ocp4_workload_athena_tenant_deploy_retries }}"
  delay: "{{ ocp4_workload_athena_tenant_deploy_retry_delay }}"
  until:
    - r_athena_deploy.resources | length > 0
    - r_athena_deploy.resources[0].status.readyReplicas is defined
    - r_athena_deploy.resources[0].status.readyReplicas >= 1
```

- [ ] **Step 2: Validate YAML syntax**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && python -c "import yaml; yaml.safe_load(open('roles/ocp4_workload_athena_tenant/tasks/workload.yml')); print('YAML OK')"`

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/tasks/workload.yml
git commit -m "feat(athena): add Helm deployment and readiness tasks"
```

---

### Task 6: Add Webhook Registration, User Info, and Cleanup

**Files:**
- Modify: `roles/ocp4_workload_athena_tenant/tasks/workload.yml` (append)

Append the final steps:
1. Look up the Athena Route URL
2. Update the AAP2 notification template with the correct external URL using `ansible.controller.notification_template`
3. Attach the notification template to all job templates in the org
4. Save connection info to `agnosticd_user_info`
5. Clean up temp files

The notification template name `athena-webhook` matches what Athena's startup code creates (see `athena/adapters/aap2.py:129`). Using the same name ensures the `ansible.controller.notification_template` module updates the existing template rather than creating a duplicate.

- [ ] **Step 1: Append webhook registration and cleanup tasks to workload.yml**

Append the following to the end of `roles/ocp4_workload_athena_tenant/tasks/workload.yml`:

```yaml

# -------------------------------------------------------------------
# 9. Get Athena route URL for webhook registration
# -------------------------------------------------------------------
- name: Get Athena route
  kubernetes.core.k8s_info:
    api_version: route.openshift.io/v1
    kind: Route
    name: "{{ ocp4_workload_athena_tenant_release_name }}"
    namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
  register: r_athena_route

- name: Set Athena URL fact
  ansible.builtin.set_fact:
    _ocp4_workload_athena_tenant_url: >-
      https://{{ r_athena_route.resources[0].spec.host }}

# -------------------------------------------------------------------
# 10. Register AAP2 webhook notification template
# -------------------------------------------------------------------
- name: Create or update AAP2 webhook notification template
  ansible.controller.notification_template:
    name: athena-webhook
    description: "Athena AIOps failure notification webhook"
    organization: "{{ ocp4_workload_athena_tenant_aap2_organization }}"
    notification_type: webhook
    notification_configuration:
      url: "{{ _ocp4_workload_athena_tenant_url }}/api/v1/webhook/aap2"
      http_method: POST
      headers:
        Content-Type: application/json
    state: present
    controller_host: "{{ _ocp4_workload_athena_tenant_aap2_url }}"
    controller_username: "{{ _ocp4_workload_athena_tenant_aap2_username }}"
    controller_password: "{{ _ocp4_workload_athena_tenant_aap2_password }}"
    validate_certs: "{{ ocp4_workload_athena_tenant_aap2_validate_certs }}"

- name: Get all job templates in tenant org
  ansible.builtin.uri:
    url: "{{ _ocp4_workload_athena_tenant_aap2_url }}/api/controller/v2/job_templates/"
    method: GET
    user: "{{ _ocp4_workload_athena_tenant_aap2_username }}"
    password: "{{ _ocp4_workload_athena_tenant_aap2_password }}"
    force_basic_auth: true
    validate_certs: "{{ ocp4_workload_athena_tenant_aap2_validate_certs }}"
    status_code: 200
  register: r_job_templates
  no_log: true

- name: Get notification template ID
  ansible.builtin.uri:
    url: "{{ _ocp4_workload_athena_tenant_aap2_url }}/api/controller/v2/notification_templates/"
    method: GET
    user: "{{ _ocp4_workload_athena_tenant_aap2_username }}"
    password: "{{ _ocp4_workload_athena_tenant_aap2_password }}"
    force_basic_auth: true
    validate_certs: "{{ ocp4_workload_athena_tenant_aap2_validate_certs }}"
    body_format: json
    status_code: 200
  register: r_notification_templates
  no_log: true

- name: Set notification template ID fact
  ansible.builtin.set_fact:
    _ocp4_workload_athena_tenant_notification_template_id: >-
      {{ r_notification_templates.json.results
         | selectattr('name', 'equalto', 'athena-webhook')
         | map(attribute='id') | first }}

- name: Attach webhook to job templates as failure notification
  ansible.builtin.uri:
    url: >-
      {{ _ocp4_workload_athena_tenant_aap2_url }}/api/controller/v2/job_templates/{{ jt_item.id }}/notification_templates_error/
    method: POST
    user: "{{ _ocp4_workload_athena_tenant_aap2_username }}"
    password: "{{ _ocp4_workload_athena_tenant_aap2_password }}"
    force_basic_auth: true
    validate_certs: "{{ ocp4_workload_athena_tenant_aap2_validate_certs }}"
    body_format: json
    body:
      id: "{{ _ocp4_workload_athena_tenant_notification_template_id }}"
    status_code:
      - 200
      - 204
  loop: "{{ r_job_templates.json.results }}"
  loop_control:
    loop_var: jt_item
    label: "{{ jt_item.name }}"
  no_log: true

# -------------------------------------------------------------------
# 11. Save connection info
# -------------------------------------------------------------------
- name: Save Athena connection info to agnosticd_user_info
  agnosticd.core.agnosticd_user_info:
    data:
      athena_url: "{{ _ocp4_workload_athena_tenant_url }}"
      athena_webhook_url: "{{ _ocp4_workload_athena_tenant_url }}/api/v1/webhook/aap2"

# -------------------------------------------------------------------
# 12. Cleanup temp files
# -------------------------------------------------------------------
- name: Clean up Athena temp files
  ansible.builtin.file:
    path: "{{ cleanup_item }}"
    state: absent
  loop:
    - /tmp/athena-helm
    - /tmp/athena-helm-values.yaml
  loop_control:
    loop_var: cleanup_item
```

- [ ] **Step 2: Validate YAML syntax**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && python -c "import yaml; yaml.safe_load(open('roles/ocp4_workload_athena_tenant/tasks/workload.yml')); print('YAML OK')"`

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/tasks/workload.yml
git commit -m "feat(athena): add webhook registration, user info, and cleanup tasks"
```

---

### Task 7: Write Removal Tasks

**Files:**
- Create: `roles/ocp4_workload_athena_tenant/tasks/remove_workload.yml`

Removal order:
1. Read AAP2 admin creds (needed to remove notification template)
2. Remove the AAP2 notification template
3. Remove the Athena Helm release
4. Delete the `aiops` bot user from Rocket.Chat
5. Remove the SCC rolebinding

Pattern reference: `roles/ocp4_workload_kira_tenant/tasks/remove_workload.yml` and `roles/ocp4_workload_aap2_tenant_config/tasks/remove_workload.yml` (which reads admin creds before cleanup).

- [ ] **Step 1: Create tasks/remove_workload.yml**

```yaml
---
# ===================================================================
# Remove Athena AIOps service
# ===================================================================

# -------------------------------------------------------------------
# 0. Read AAP2 admin credentials (needed to remove notification template)
# -------------------------------------------------------------------
- name: Get AAP admin credentials secret
  kubernetes.core.k8s_info:
    api_version: v1
    kind: Secret
    name: "{{ ocp4_workload_athena_tenant_aap2_admin_secret }}"
    namespace: "{{ ocp4_workload_athena_tenant_aap2_admin_namespace }}"
  register: r_aap_admin_secret

- name: Remove AAP2 resources if admin credentials exist
  when: r_aap_admin_secret.resources | length > 0
  block:
    - name: Extract AAP admin credentials from secret
      ansible.builtin.set_fact:
        _ocp4_workload_athena_tenant_aap2_url: >-
          {{ r_aap_admin_secret.resources[0].data.url | b64decode }}
        _ocp4_workload_athena_tenant_aap2_username: >-
          {{ r_aap_admin_secret.resources[0].data.username | b64decode }}
        _ocp4_workload_athena_tenant_aap2_password: >-
          {{ r_aap_admin_secret.resources[0].data.password | b64decode }}
      no_log: true

    # -----------------------------------------------------------------
    # 1. Remove AAP2 notification template
    # -----------------------------------------------------------------
    - name: Remove AAP2 webhook notification template
      ansible.controller.notification_template:
        name: athena-webhook
        organization: "{{ ocp4_workload_athena_tenant_aap2_organization }}"
        state: absent
        controller_host: "{{ _ocp4_workload_athena_tenant_aap2_url }}"
        controller_username: "{{ _ocp4_workload_athena_tenant_aap2_username }}"
        controller_password: "{{ _ocp4_workload_athena_tenant_aap2_password }}"
        validate_certs: "{{ ocp4_workload_athena_tenant_aap2_validate_certs }}"
      ignore_errors: true

# -------------------------------------------------------------------
# 2. Remove Athena Helm release
# -------------------------------------------------------------------
- name: Remove Athena Helm release
  kubernetes.core.helm:
    name: "{{ ocp4_workload_athena_tenant_release_name }}"
    release_namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
    state: absent
    wait: true

# -------------------------------------------------------------------
# 3. Remove aiops bot user from Rocket.Chat
# -------------------------------------------------------------------
- name: Get Rocket.Chat route
  kubernetes.core.k8s_info:
    api_version: route.openshift.io/v1
    kind: Route
    name: rocketchat
    namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
  register: r_rocketchat_route

- name: Remove aiops bot user if Rocket.Chat is still running
  when: r_rocketchat_route.resources | length > 0
  block:
    - name: Login to Rocket.Chat as admin
      ansible.builtin.uri:
        url: "https://{{ r_rocketchat_route.resources[0].spec.host }}/api/v1/login"
        method: POST
        body_format: json
        body:
          user: "{{ ocp4_workload_athena_tenant_rocketchat_admin_username }}"
          password: "{{ ocp4_workload_athena_tenant_rocketchat_admin_password }}"
        status_code: 200
        validate_certs: false
      register: r_rc_admin_login
      no_log: true
      ignore_errors: true

    - name: Look up aiops bot user ID
      when: r_rc_admin_login is succeeded
      ansible.builtin.uri:
        url: >-
          https://{{ r_rocketchat_route.resources[0].spec.host }}/api/v1/users.info?username={{ ocp4_workload_athena_tenant_rocketchat_bot_username }}
        method: GET
        headers:
          X-Auth-Token: "{{ r_rc_admin_login.json.data.authToken }}"
          X-User-Id: "{{ r_rc_admin_login.json.data.userId }}"
        status_code:
          - 200
          - 400
        validate_certs: false
      register: r_rc_bot_info
      no_log: true
      ignore_errors: true

    - name: Delete aiops bot user
      when:
        - r_rc_bot_info is succeeded
        - r_rc_bot_info.status == 200
      ansible.builtin.uri:
        url: "https://{{ r_rocketchat_route.resources[0].spec.host }}/api/v1/users.delete"
        method: POST
        headers:
          X-Auth-Token: "{{ r_rc_admin_login.json.data.authToken }}"
          X-User-Id: "{{ r_rc_admin_login.json.data.userId }}"
        body_format: json
        body:
          userId: "{{ r_rc_bot_info.json.user._id }}"
        status_code:
          - 200
          - 400
        validate_certs: false
      register: r_rc_bot_delete
      changed_when: r_rc_bot_delete.status == 200
      ignore_errors: true

# -------------------------------------------------------------------
# 4. Remove anyuid SCC rolebinding
# -------------------------------------------------------------------
- name: Remove anyuid SCC rolebinding
  kubernetes.core.k8s:
    state: absent
    api_version: rbac.authorization.k8s.io/v1
    kind: RoleBinding
    name: athena-anyuid
    namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
```

- [ ] **Step 2: Validate YAML syntax**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && python -c "import yaml; yaml.safe_load(open('roles/ocp4_workload_athena_tenant/tasks/remove_workload.yml')); print('YAML OK')"`

Expected: `YAML OK`

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/tasks/remove_workload.yml
git commit -m "feat(athena): add removal tasks for clean teardown"
```

---

### Task 8: Final Validation

**Files:** (no changes — validation only)

- [ ] **Step 1: Verify complete file tree**

Run: `find /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_athena_tenant -type f | sort`

Expected:
```
roles/ocp4_workload_athena_tenant/defaults/main.yml
roles/ocp4_workload_athena_tenant/tasks/main.yml
roles/ocp4_workload_athena_tenant/tasks/remove_workload.yml
roles/ocp4_workload_athena_tenant/tasks/workload.yml
roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2
```

- [ ] **Step 2: Validate all YAML files parse cleanly**

Run: `cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops && python -c "import yaml; [yaml.safe_load(open(f)) for f in ['roles/ocp4_workload_athena_tenant/defaults/main.yml', 'roles/ocp4_workload_athena_tenant/tasks/main.yml', 'roles/ocp4_workload_athena_tenant/tasks/workload.yml', 'roles/ocp4_workload_athena_tenant/tasks/remove_workload.yml']]; print('All YAML OK')"`

Expected: `All YAML OK`

- [ ] **Step 3: Verify variable consistency**

Spot-check that every `_ocp4_workload_athena_tenant_*` internal fact set in `workload.yml` is consumed by `templates/helm-values.yaml.j2`:

| Internal fact (set_fact) | Used in template |
|---|---|
| `_ocp4_workload_athena_tenant_aap2_url` | `aap2.url` |
| `_ocp4_workload_athena_tenant_aap2_username` | `aap2.username` |
| `_ocp4_workload_athena_tenant_aap2_password` | `aap2.password` |
| `_ocp4_workload_athena_tenant_kira_api_host` | `kira.url` |
| `_ocp4_workload_athena_tenant_kira_frontend_host` | `kira.frontendUrl` |
| `_ocp4_workload_athena_tenant_rocketchat_host` | `rocketchat.url` |
| `_ocp4_workload_athena_tenant_rocketchat_auth_token` | `rocketchat.apiAuthToken` |
| `_ocp4_workload_athena_tenant_rocketchat_user_id` | `rocketchat.apiUserId` |

All internal facts are produced before the template task (Step 7) and consumed in the template. No orphaned or missing variables.

- [ ] **Step 4: Push to remote**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git push
```

---

## Notes

**AgnosticV catalog update:** After this role is merged, the tenant catalog item at `lb2645-agentic-devops-tenant/common.yaml` needs the new workload added between `rocketchat_tenant` and `showroom`:

```yaml
  - rhpds.deepagents_aiops.ocp4_workload_athena_tenant
```

This is in a separate repo (`rhpds/agnosticv`, branch `ci/lb2645-kira-tty-and-new-models`) and should be done as a follow-up after the role is available.

**Athena startup webhook:** Athena's startup code (`app.py:60`) uses `ATHENA_BASE_URL` or falls back to `http://athena:8080`. The role does not set `ATHENA_BASE_URL` — the startup creates the notification template with the internal URL (which makes `readyz` pass), and then the role updates it with the correct external Route URL in Step 10. This avoids a two-phase deployment.
