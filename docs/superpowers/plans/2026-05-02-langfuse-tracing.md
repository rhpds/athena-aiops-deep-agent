# LangFuse Tracing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in LangFuse observability to Athena and a showroom lab module so students can explore agent traces.

**Architecture:** LangFuse's `CallbackHandler` auto-instruments all LangChain/LangGraph activity. Athena sets env vars; LangFuse auto-reads them. Per-tenant LangFuse instances deployed via the official Helm chart. A new showroom module walks students through exploring traces.

**Tech Stack:** LangFuse Python SDK, official `langfuse/langfuse` Helm chart, Ansible deployer roles, AsciiDoc showroom content.

**Spec:** `docs/superpowers/specs/2026-05-02-langfuse-tracing-design.md`

**Repos:**
- Athena: `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent`
- Deployer: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops`
- Showroom: `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops` (branch `tok-01`)

---

### File Map

| File | Repo | Action | Responsibility |
|------|------|--------|---------------|
| `pyproject.toml` | Athena | Modify | Add `langfuse` dependency |
| `athena/config.py` | Athena | Modify | Add 3 optional LangFuse env vars |
| `athena/app.py` | Athena | Modify | Register callback handler in lifespan |
| `deploy/helm/athena/values.yaml` | Athena | Modify | Add `langfuse.*` values |
| `deploy/helm/athena/templates/deployment.yaml` | Athena | Modify | Wire LangFuse env vars |
| `deploy/helm/athena/templates/secret.yaml` | Athena | Modify | Include LangFuse secret key |
| `roles/ocp4_workload_langfuse_tenant/` | Deployer | Create | New role: deploy LangFuse per tenant |
| `roles/ocp4_workload_athena_tenant/defaults/main.yml` | Deployer | Modify | Add LangFuse defaults |
| `roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2` | Deployer | Modify | Wire LangFuse values |
| `content/modules/ROOT/pages/09-module-07-tracing.adoc` | Showroom | Create | New lab module |
| `content/modules/ROOT/nav.adoc` | Showroom | Modify | Add module to nav |

**Note:** The LangFuse Helm chart is the official upstream chart from `https://langfuse.github.io/langfuse-k8s`. We deploy it via `helm repo add` in the deployer role — no custom chart needed.

---

### Task 1: Add LangFuse dependency to Athena

**Files:**
- Modify: `pyproject.toml:6-19` (dependencies list)

- [ ] **Step 1: Add langfuse to dependencies**

In `pyproject.toml`, add `"langfuse>=2.0",` to the dependencies list, after `"jinja2"`:

```toml
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.34",
    "httpx>=0.28",
    "pydantic>=2.10",
    "pydantic-settings>=2.7",
    "deepagents",
    "langchain-core",
    "langchain-anthropic",
    "langchain-openai",
    "tavily-python",
    "pyyaml",
    "rich",
    "jinja2",
    "langfuse>=2.0",
]
```

- [ ] **Step 2: Sync dependencies**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent && uv sync`

Expected: Resolves and installs langfuse.

- [ ] **Step 3: Verify langfuse is importable**

Run: `uv run python -c "import langfuse; print(langfuse.__version__)"`

Expected: Prints a version number (e.g., `2.x.x`).

- [ ] **Step 4: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
git add pyproject.toml uv.lock
git commit -m "feat: add langfuse dependency for tracing"
```

---

### Task 2: Add LangFuse config to Settings

**Files:**
- Modify: `athena/config.py:34-39` (Optional settings section)

- [ ] **Step 1: Add LangFuse settings**

Add three optional fields at the end of the `Settings` class, after `athena_base_url`:

```python
    # LangFuse tracing (opt-in — if unset, no tracing)
    langfuse_secret_key: SecretStr | None = None
    langfuse_public_key: str | None = None
    langfuse_host: str | None = None
```

The full `Settings` class ends as:

```python
    # Athena service
    athena_webhook_path: str = "/api/v1/webhook/aap2"
    athena_base_url: str | None = None

    # LangFuse tracing (opt-in — if unset, no tracing)
    langfuse_secret_key: SecretStr | None = None
    langfuse_public_key: str | None = None
    langfuse_host: str | None = None
```

- [ ] **Step 2: Verify Settings loads**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent && uv run python -c "from athena.config import Settings; print('langfuse_secret_key' in Settings.model_fields)"`

Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add athena/config.py
git commit -m "feat: add optional LangFuse config settings"
```

---

### Task 3: Register LangFuse callback in app lifespan

**Files:**
- Modify: `athena/app.py:20-70` (lifespan function)

- [ ] **Step 1: Add LangFuse callback registration**

In `athena/app.py`, add the following block inside the `lifespan()` function, after the Tavily env var setup (after line 34) and before the adapter client initialization (before line 37):

```python
    # LangFuse tracing (opt-in)
    if settings.langfuse_secret_key:
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key.get_secret_value()
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key or ""
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host or ""
        from langfuse.callback import CallbackHandler
        langfuse_handler = CallbackHandler()
        langfuse_handler.auth_check()
        logger.info("LangFuse tracing enabled → %s", settings.langfuse_host)
```

The `CallbackHandler()` constructor auto-reads from the env vars we just set. The `auth_check()` call verifies connectivity at startup — it logs a warning if LangFuse is unreachable but doesn't raise.

The env-var approach means LangChain's internal instrumentation auto-discovers LangFuse for all operations, including LangGraph subgraph calls. No changes to `pipeline.py`.

- [ ] **Step 2: Run existing tests to verify no breakage**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent && uv run pytest tests/ -v`

Expected: All tests pass. The LangFuse code path is never executed in tests because `langfuse_secret_key` defaults to `None`.

- [ ] **Step 3: Commit**

```bash
git add athena/app.py
git commit -m "feat: register LangFuse callback handler in app lifespan"
```

---

### Task 4: Wire LangFuse env vars into Athena Helm chart

**Files:**
- Modify: `deploy/helm/athena/values.yaml:28-29`
- Modify: `deploy/helm/athena/templates/deployment.yaml:108-114`
- Modify: `deploy/helm/athena/templates/secret.yaml:13-15`

- [ ] **Step 1: Add LangFuse values**

In `deploy/helm/athena/values.yaml`, add a `langfuse` section after `tavily`:

```yaml
tavily:
  apiKey: ""

langfuse:
  secretKey: ""
  publicKey: ""
  host: ""
```

- [ ] **Step 2: Add LangFuse env vars to deployment template**

In `deploy/helm/athena/templates/deployment.yaml`, add the following block after the `ATHENA_BASE_URL` conditional block (after line 114, before the `livenessProbe`):

```yaml
            {{- if .Values.langfuse.secretKey }}
            - name: LANGFUSE_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: {{ include "athena.fullname" . }}
                  key: langfuse-secret-key
            - name: LANGFUSE_PUBLIC_KEY
              value: {{ .Values.langfuse.publicKey | quote }}
            - name: LANGFUSE_HOST
              value: {{ .Values.langfuse.host | quote }}
            {{- end }}
```

- [ ] **Step 3: Add LangFuse secret key to secret template**

In `deploy/helm/athena/templates/secret.yaml`, add after the tavily conditional block (after line 15):

```yaml
  {{- if .Values.langfuse.secretKey }}
  langfuse-secret-key: {{ .Values.langfuse.secretKey | quote }}
  {{- end }}
```

- [ ] **Step 4: Validate Helm template renders**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent && helm template test deploy/helm/athena/ --set langfuse.secretKey=sk-test --set langfuse.publicKey=pk-test --set langfuse.host=http://langfuse:3000 2>&1 | grep -A2 LANGFUSE`

Expected: Shows all three LANGFUSE env vars in the rendered output.

- [ ] **Step 5: Verify without LangFuse values (no env vars rendered)**

Run: `helm template test deploy/helm/athena/ 2>&1 | grep LANGFUSE`

Expected: No output (LangFuse env vars are not rendered when values are empty).

- [ ] **Step 6: Commit**

```bash
git add deploy/helm/athena/values.yaml deploy/helm/athena/templates/deployment.yaml deploy/helm/athena/templates/secret.yaml
git commit -m "feat: wire LangFuse env vars into Athena Helm chart"
```

---

### Task 5: Create LangFuse deployer role

This role deploys LangFuse per tenant using the official upstream Helm chart.

**Files:**
- Create: `roles/ocp4_workload_langfuse_tenant/defaults/main.yml`
- Create: `roles/ocp4_workload_langfuse_tenant/tasks/main.yml`
- Create: `roles/ocp4_workload_langfuse_tenant/tasks/workload.yml`
- Create: `roles/ocp4_workload_langfuse_tenant/tasks/remove_workload.yml`
- Create: `roles/ocp4_workload_langfuse_tenant/templates/helm-values.yaml.j2`

All files in repo: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops`

- [ ] **Step 1: Create defaults/main.yml**

Create `roles/ocp4_workload_langfuse_tenant/defaults/main.yml`:

```yaml
---
# ===================================================================
# Role: ocp4_workload_langfuse_tenant
# Deploys LangFuse observability per tenant via official Helm chart.
# ===================================================================

# Target namespace (defaults to existing tenant namespace)
ocp4_workload_langfuse_tenant_namespace: "{{ ocp4_workload_username }}-agentic"

# Helm chart source (official upstream)
ocp4_workload_langfuse_tenant_helm_repo_name: langfuse
ocp4_workload_langfuse_tenant_helm_repo_url: https://langfuse.github.io/langfuse-k8s
ocp4_workload_langfuse_tenant_helm_chart_version: ""

# Helm release name
ocp4_workload_langfuse_tenant_release_name: langfuse

# LangFuse configuration
ocp4_workload_langfuse_tenant_salt: "{{ common_password | default('langfuse-salt') }}"
ocp4_workload_langfuse_tenant_nextauth_secret: "{{ common_password | default('langfuse-nextauth') }}"
ocp4_workload_langfuse_tenant_encryption_key: "{{ common_password | default('langfuse-encryption-key-32chars!!') }}"

# PostgreSQL (bundled with the Helm chart)
ocp4_workload_langfuse_tenant_postgres_password: "{{ common_password | default('langfuse') }}"

# Initial admin user
ocp4_workload_langfuse_tenant_admin_email: "admin@example.com"
ocp4_workload_langfuse_tenant_admin_password: "{{ common_password | default('admin123') }}"

# Retry configuration
ocp4_workload_langfuse_tenant_deploy_retries: 60
ocp4_workload_langfuse_tenant_deploy_retry_delay: 10
```

- [ ] **Step 2: Create tasks/main.yml**

Create `roles/ocp4_workload_langfuse_tenant/tasks/main.yml`:

```yaml
---
- name: Running role ocp4_workload_langfuse_tenant
  ansible.builtin.debug:
    msg: "Running role ocp4_workload_langfuse_tenant"

- name: Run workload
  when: ACTION == "create" or ACTION == "provision"
  ansible.builtin.include_tasks: workload.yml

- name: Remove workload
  when: ACTION == "destroy" or ACTION == "remove"
  ansible.builtin.include_tasks: remove_workload.yml
```

- [ ] **Step 3: Create tasks/workload.yml**

Create `roles/ocp4_workload_langfuse_tenant/tasks/workload.yml`:

```yaml
---
# ===================================================================
# Deploy LangFuse per tenant via official Helm chart
# ===================================================================

# -------------------------------------------------------------------
# 1. Add Helm repo
# -------------------------------------------------------------------
- name: Add LangFuse Helm repository
  kubernetes.core.helm_repository:
    name: "{{ ocp4_workload_langfuse_tenant_helm_repo_name }}"
    repo_url: "{{ ocp4_workload_langfuse_tenant_helm_repo_url }}"

# -------------------------------------------------------------------
# 2. Generate Helm values
# -------------------------------------------------------------------
- name: Template Helm values file
  ansible.builtin.template:
    src: helm-values.yaml.j2
    dest: /tmp/langfuse-helm-values.yaml
    mode: "0644"

# -------------------------------------------------------------------
# 3. Deploy via Helm
# -------------------------------------------------------------------
- name: Deploy LangFuse via Helm
  kubernetes.core.helm:
    name: "{{ ocp4_workload_langfuse_tenant_release_name }}"
    chart_ref: "{{ ocp4_workload_langfuse_tenant_helm_repo_name }}/langfuse"
    release_namespace: "{{ ocp4_workload_langfuse_tenant_namespace }}"
    values_files:
      - /tmp/langfuse-helm-values.yaml
    state: present
    wait: false

# -------------------------------------------------------------------
# 4. Create OpenShift Route for LangFuse UI
# -------------------------------------------------------------------
- name: Create LangFuse route
  kubernetes.core.k8s:
    state: present
    definition:
      apiVersion: route.openshift.io/v1
      kind: Route
      metadata:
        name: langfuse
        namespace: "{{ ocp4_workload_langfuse_tenant_namespace }}"
      spec:
        to:
          kind: Service
          name: "{{ ocp4_workload_langfuse_tenant_release_name }}-web"
          weight: 100
        port:
          targetPort: http
        tls:
          termination: edge
          insecureEdgeTerminationPolicy: Redirect

# -------------------------------------------------------------------
# 5. Wait for LangFuse to be ready
# -------------------------------------------------------------------
- name: Wait for LangFuse web deployment to be available
  kubernetes.core.k8s_info:
    api_version: apps/v1
    kind: Deployment
    name: "{{ ocp4_workload_langfuse_tenant_release_name }}-web"
    namespace: "{{ ocp4_workload_langfuse_tenant_namespace }}"
  register: r_langfuse_deploy
  retries: "{{ ocp4_workload_langfuse_tenant_deploy_retries }}"
  delay: "{{ ocp4_workload_langfuse_tenant_deploy_retry_delay }}"
  until:
    - r_langfuse_deploy.resources | length > 0
    - r_langfuse_deploy.resources[0].status.readyReplicas is defined
    - r_langfuse_deploy.resources[0].status.readyReplicas >= 1

# -------------------------------------------------------------------
# 6. Discover LangFuse route URL
# -------------------------------------------------------------------
- name: Get LangFuse route
  kubernetes.core.k8s_info:
    api_version: route.openshift.io/v1
    kind: Route
    name: langfuse
    namespace: "{{ ocp4_workload_langfuse_tenant_namespace }}"
  register: r_langfuse_route

- name: Set LangFuse URL facts
  ansible.builtin.set_fact:
    _ocp4_workload_langfuse_tenant_url: "https://{{ r_langfuse_route.resources[0].spec.host }}"
    _ocp4_workload_langfuse_tenant_internal_url: "http://{{ ocp4_workload_langfuse_tenant_release_name }}-web.{{ ocp4_workload_langfuse_tenant_namespace }}.svc.cluster.local:3000"

# -------------------------------------------------------------------
# 7. Create initial project and API keys via LangFuse API
# -------------------------------------------------------------------
- name: Wait for LangFuse API to be responsive
  ansible.builtin.uri:
    url: "{{ _ocp4_workload_langfuse_tenant_url }}/api/public/health"
    method: GET
    validate_certs: false
    status_code: 200
  register: r_langfuse_health
  retries: 30
  delay: 10
  until: r_langfuse_health is succeeded

# -------------------------------------------------------------------
# 8. Save connection info
# -------------------------------------------------------------------
- name: Save LangFuse connection info to agnosticd_user_info
  agnosticd.core.agnosticd_user_info:
    data:
      langfuse_url: "{{ _ocp4_workload_langfuse_tenant_url }}"
      langfuse_internal_url: "{{ _ocp4_workload_langfuse_tenant_internal_url }}"
      langfuse_admin_email: "{{ ocp4_workload_langfuse_tenant_admin_email }}"
      langfuse_admin_password: "{{ ocp4_workload_langfuse_tenant_admin_password }}"

# -------------------------------------------------------------------
# 9. Cleanup temp files
# -------------------------------------------------------------------
- name: Clean up LangFuse temp files
  ansible.builtin.file:
    path: /tmp/langfuse-helm-values.yaml
    state: absent
```

- [ ] **Step 4: Create tasks/remove_workload.yml**

Create `roles/ocp4_workload_langfuse_tenant/tasks/remove_workload.yml`:

```yaml
---
- name: Remove LangFuse Helm release
  kubernetes.core.helm:
    name: "{{ ocp4_workload_langfuse_tenant_release_name }}"
    release_namespace: "{{ ocp4_workload_langfuse_tenant_namespace }}"
    state: absent
    wait: true

- name: Remove LangFuse route
  kubernetes.core.k8s:
    api_version: route.openshift.io/v1
    kind: Route
    name: langfuse
    namespace: "{{ ocp4_workload_langfuse_tenant_namespace }}"
    state: absent
```

- [ ] **Step 5: Create templates/helm-values.yaml.j2**

Create `roles/ocp4_workload_langfuse_tenant/templates/helm-values.yaml.j2`:

```yaml
langfuse:
  salt:
    value: "{{ ocp4_workload_langfuse_tenant_salt }}"
  nextauth:
    secret:
      value: "{{ ocp4_workload_langfuse_tenant_nextauth_secret }}"
    url: "{{ _ocp4_workload_langfuse_tenant_url | default('http://localhost:3000') }}"
  encryptionKey:
    value: "{{ ocp4_workload_langfuse_tenant_encryption_key }}"
  init:
    user:
      name: Admin
      email: "{{ ocp4_workload_langfuse_tenant_admin_email }}"
      password: "{{ ocp4_workload_langfuse_tenant_admin_password }}"
    org:
      name: "{{ ocp4_workload_langfuse_tenant_namespace }}"
    project:
      name: athena

postgresql:
  auth:
    username: langfuse
    password: "{{ ocp4_workload_langfuse_tenant_postgres_password }}"

clickhouse:
  auth:
    password: "{{ ocp4_workload_langfuse_tenant_postgres_password }}"

redis:
  auth:
    password: "{{ ocp4_workload_langfuse_tenant_postgres_password }}"

s3:
  auth:
    rootPassword: "{{ ocp4_workload_langfuse_tenant_postgres_password }}"
```

- [ ] **Step 6: Verify role structure**

Run: `find /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_langfuse_tenant -type f | sort`

Expected:
```
.../defaults/main.yml
.../tasks/main.yml
.../tasks/remove_workload.yml
.../tasks/workload.yml
.../templates/helm-values.yaml.j2
```

- [ ] **Step 7: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_langfuse_tenant/
git commit -m "feat: add ocp4_workload_langfuse_tenant deployer role"
```

---

### Task 6: Wire LangFuse into Athena deployer

**Files:**
- Modify: `roles/ocp4_workload_athena_tenant/defaults/main.yml`
- Modify: `roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2`

Both in repo: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops`

- [ ] **Step 1: Add LangFuse defaults to Athena tenant role**

In `roles/ocp4_workload_athena_tenant/defaults/main.yml`, add after the `athena_base_url` line (or at the end, before retry config):

```yaml
# LangFuse tracing (opt-in — leave empty to disable)
ocp4_workload_athena_tenant_langfuse_secret_key: ""
ocp4_workload_athena_tenant_langfuse_public_key: ""
ocp4_workload_athena_tenant_langfuse_host: ""
```

- [ ] **Step 2: Add LangFuse values to Helm values template**

In `roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2`, add at the end of the file (after the `resources` block):

```yaml
{% if ocp4_workload_athena_tenant_langfuse_secret_key | default('') | length > 0 %}
langfuse:
  secretKey: "{{ ocp4_workload_athena_tenant_langfuse_secret_key }}"
  publicKey: "{{ ocp4_workload_athena_tenant_langfuse_public_key }}"
  host: "{{ ocp4_workload_athena_tenant_langfuse_host }}"
{% endif %}
```

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/defaults/main.yml roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2
git commit -m "feat: wire LangFuse env vars into Athena deployer"
```

---

### Task 7: Create showroom lab module

**Files:**
- Create: `content/modules/ROOT/pages/09-module-07-tracing.adoc`
- Modify: `content/modules/ROOT/nav.adoc`

Repo: `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops` (branch `tok-01`)

- [ ] **Step 1: Verify you're on the tok-01 branch**

Run: `cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops && git branch --show-current`

Expected: `tok-01`

- [ ] **Step 2: Create the tracing module**

Create `content/modules/ROOT/pages/09-module-07-tracing.adoc`:

```asciidoc
= Module 7: Observing the Agent Pipeline
:source-highlighter: rouge
:toc: macro
:toclevels: 1

You've seen Athena analyze failures and create tickets.
But what's happening inside the pipeline?
How does ops_manager decide which specialist to call?
What does an SRE agent actually do when it "comes to life"?

In this module, you'll use LangFuse — an open-source LLM observability platform — to see exactly how the agent pipeline works, from classification through delegation to ticket creation.

toc::[]

== Learning objectives

By the end of this module, you'll be able to:

* Navigate the LangFuse trace view to understand agent execution flow
* Identify how ops_manager classifies failures and selects specialist agents
* Observe the lifecycle of an SRE subagent — skill loading, context reading, analysis
* Understand model routing decisions (which model handles which task and why)
* Read token usage and latency metrics to understand cost and performance

== Open LangFuse

Your environment includes a pre-configured LangFuse instance that's already wired to Athena.

. Open the *LangFuse* tab in the top navigation bar
. Log in with your credentials:
+
[cols="1,2"]
|===
| Email | `{langfuse_admin_email}`
| Password | `{langfuse_admin_password}`
|===

You should see the LangFuse dashboard with a project called *athena*.

== Trigger a failure

Let's generate a trace by triggering a failed AAP2 job.

. Switch to the *AAP2* tab
. Navigate to *Automation Execution → Templates*
. Find the *10 Install Python 3.14* job template and click the launch icon
. Wait for the job to fail (about 15 seconds)

Athena will receive the failure webhook, analyze it through the agent pipeline, and create a Kira ticket — just as in earlier modules.
But this time, every step is being traced.

== Find the trace

. Switch back to the *LangFuse* tab
. Click *Traces* in the left sidebar
. You should see a new trace appear within 30–60 seconds
+
NOTE: The trace appears after Athena finishes processing. If you don't see it immediately, wait a moment and refresh.

. Click on the trace to open the detail view

== Explore the agent lifecycle

The trace shows the full execution hierarchy.
Let's walk through each layer.

=== ops_manager: The coordinator

The root of the trace is the `ops_manager` agent.
This is the main orchestrator that:

. Reads the incident context (`incident.json`)
. Loads the `error-classifier` skill
. Makes an LLM call to classify the failure domain
. Delegates to a specialist SRE agent

Look for the first LLM call — this is where ops_manager reads the error-classifier skill and determines:

* *Domain*: `linux` (this is a package management issue)
* *Confidence*: 90%+
* *Delegate to*: `sre_linux`

=== sre_linux: The specialist comes to life

Expand the `task` tool call that delegates to `sre_linux`.
Inside, you'll see a new agent generation — the SRE specialist.

Watch its lifecycle:

. *Skill loading*: `read_file` calls to `skills/analyze-linux-failure/SKILL.md` — this skill guides the agent's analysis approach
. *Context reading*: `read_file` call to `incident.json` — the agent reads the same incident data ops_manager received
. *Root cause analysis*: One or more LLM calls where the agent reasons about the failure
. *Formatted output*: A final LLM call producing structured analysis

This is the core of the Deep Agents pattern — each specialist loads domain-specific skills that guide its reasoning, then applies that expertise to the incident.

=== reviewer: Quality gate

After the SRE specialist returns its analysis, ops_manager delegates to the `reviewer` agent.

Notice:

* The reviewer uses *claude-3-5-haiku* — a faster, cheaper model
* Its job is validation, not analysis — checking coherence, completeness, and actionability
* This is a cost optimization: expensive reasoning models for analysis, cheap models for review

=== Final output

The last LLM call in the ops_manager trace produces the `TicketPayload` JSON — the structured data that becomes a Kira ticket.

Expand it to see the complete payload: title, description, area, confidence, risk, recommended action, affected systems, and skills.

== Key observations

Take a moment to examine these aspects of the trace:

=== Token usage

Each LLM call shows input and output token counts.

* How many total tokens does a single incident analysis consume?
* Which agent uses the most tokens?
* How does the reviewer's token usage compare to the specialist's?

=== Latency

The trace timeline shows how long each step takes.

* What's the total pipeline duration?
* Which step takes the longest? (Usually the specialist RCA)
* How much time is spent on tool calls vs. LLM reasoning?

=== Model routing

Different agents use different models:

* `ops_manager` and `sre_linux`: *claude-sonnet-4-6* (capable reasoning)
* `reviewer`: *claude-3-5-haiku* (fast validation)

This is intentional — match model capability to task complexity.

=== Skill-driven behavior

The `read_file` tool calls to `skills/*/SKILL.md` files are how Deep Agents load domain expertise.
Each skill is a markdown document that guides the agent's reasoning approach.

Without skills, the agent would rely on general knowledge.
With skills, it follows a structured analysis methodology specific to the failure domain.

== Summary

In this module, you explored the inner workings of the Athena agent pipeline using LangFuse traces.
You saw how:

* *ops_manager* coordinates the pipeline — classifying, delegating, reviewing, and producing output
* *Specialist SREs* load domain skills and apply structured analysis
* *The reviewer* validates quality using a cheaper model
* *Token usage and latency* reveal the cost and performance profile of the pipeline
* *Skills* are the mechanism that gives each agent domain expertise

This observability layer is essential for understanding, debugging, and optimizing agentic systems in production.
```

- [ ] **Step 3: Add module to nav.adoc**

In `content/modules/ROOT/nav.adoc`, add the tracing module after Module 5:

```asciidoc
* xref:index.adoc[Welcome]

.Workshop
* xref:01-overview.adoc[Overview]

.Modules
* xref:03-module-01-problem-domain.adoc[Module 1: The Problem Domain]
* xref:04-module-02-environment.adoc[Module 2: Your First Failure]
* xref:05-module-03-first-agent.adoc[Module 3: Understanding your Agentic DevOps Team]
* xref:06-module-04-deep-agents.adoc[Module 4: Open Source Models]
* xref:07-module-05-compliance-loop.adoc[Module 5: Can OSS Take Full Control?]
* xref:09-module-07-tracing.adoc[Module 7: Observing the Agent Pipeline]

.Wrap-up
* xref:09-conclusion.adoc[Conclusion]
// * xref:02-details.adoc[Details & Setup]

.Bonus
* xref:10-bonus-deep-agents-deep-dive.adoc[Deep Agents Deep Dive]
```

- [ ] **Step 4: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops
git add content/modules/ROOT/pages/09-module-07-tracing.adoc content/modules/ROOT/nav.adoc
git commit -m "feat: add Module 7 — Observing the Agent Pipeline (LangFuse tracing)"
```

---

### Task 8: Push all repos

**Files:** None (push only)

- [ ] **Step 1: Push Athena repo**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
git push
```

- [ ] **Step 2: Push deployer repo**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git push
```

- [ ] **Step 3: Push showroom repo (tok-01 branch)**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops
git push origin tok-01
```
