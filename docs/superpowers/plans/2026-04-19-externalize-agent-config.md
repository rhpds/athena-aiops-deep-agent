# Externalize Agent Config and Skills Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable runtime customization of Athena's agent configuration and skills without rebuilding the container image — students can `oc edit configmap` to add subagents and `oc cp` to add skills.

**Architecture:** ConfigMap `athena-agent-config` always holds `AGENTS.md` and `subagents.yaml`, mounted into the pod. A PVC holds skills, pre-populated from the image via an initContainer on first deploy. The Ansible deployer role provides ConfigMap content from the cloned repo.

**Tech Stack:** Helm 3, Kubernetes (OpenShift), Ansible (deployer role), Dockerfile multi-stage build

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `subagents.yaml` | Modify | Drop `openai:` model prefix |
| `Dockerfile` | Modify | Add `skills-default/` copy for initContainer |
| `deploy/helm/athena/values.yaml` | Modify | Update comments, keep empty defaults |
| `deploy/helm/athena/templates/configmap.yaml` | Modify | Fixed name, remove conditionals |
| `deploy/helm/athena/templates/deployment.yaml` | Modify | Always mount ConfigMap, add initContainer |
| `roles/.../templates/helm-values.yaml.j2` | Modify | Provide ConfigMap content, enable skills PVC |

Deployer role path: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_athena_tenant/`

---

### Task 1: Drop Model Prefix from subagents.yaml

**Files:**
- Modify: `subagents.yaml:6,28,52,77,106`

- [ ] **Step 1: Remove `openai:` prefix from all model values**

In `subagents.yaml`, change all five model lines:

```yaml
# Before (lines 6, 28, 52, 77):
  model: openai:claude-sonnet-4-6
# After:
  model: claude-sonnet-4-6

# Before (line 106):
  model: openai:claude-3-5-haiku
# After:
  model: claude-3-5-haiku
```

- [ ] **Step 2: Verify parser handles bare names**

Run: `python3 -c "name = 'claude-sonnet-4-6'; print(name.split(':')[-1] if ':' in name else name)"`

Expected: `claude-sonnet-4-6`

- [ ] **Step 3: Run existing tests**

Run: `uv run pytest tests/ -q`

Expected: All tests pass (no code change to pipeline.py — parser already handles both)

- [ ] **Step 4: Commit**

```bash
git add subagents.yaml
git commit -m "chore: drop openai prefix from subagent model names

MaaS endpoint uses bare model names (claude-sonnet-4-6, claude-3-5-haiku).
The openai: prefix was informational only — stripped by pipeline.py parser.
Bare names are simpler for students editing the ConfigMap.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: Add skills-default Copy to Dockerfile

**Files:**
- Modify: `Dockerfile:15`

- [ ] **Step 1: Add skills-default copy line**

In the builder stage, after the existing `COPY skills/ skills/` line (line 15), add a second copy to create the reference directory:

```dockerfile
COPY skills/ skills/
COPY skills/ skills-default/
```

The full builder stage becomes:

```dockerfile
FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY athena/ athena/
COPY AGENTS.md subagents.yaml ./
COPY skills/ skills/
COPY skills/ skills-default/
COPY templates/ templates/

# Install the project itself
RUN uv sync --no-dev
```

- [ ] **Step 2: Verify build succeeds locally**

Run: `podman build --platform linux/amd64 -t quay.io/rhpds/athena-aiops:test-externalize . 2>&1 | tail -5`

Expected: `Successfully tagged quay.io/rhpds/athena-aiops:test-externalize`

- [ ] **Step 3: Verify skills-default exists in image**

Run: `podman run --rm quay.io/rhpds/athena-aiops:test-externalize ls /app/skills-default/`

Expected: Lists skill directories (analyze-ansible-failure, analyze-linux-failure, etc.)

- [ ] **Step 4: Commit**

```bash
git add Dockerfile
git commit -m "feat: copy skills to skills-default/ for initContainer pre-population

The PVC mounts at /app/skills/ and masks the baked-in skills.
The initContainer copies from /app/skills-default/ to the PVC on
first deploy, preserving student additions on subsequent restarts.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: Update Helm ConfigMap Template

**Files:**
- Modify: `deploy/helm/athena/templates/configmap.yaml`

- [ ] **Step 1: Replace configmap.yaml with fixed-name, unconditional version**

Replace the entire file with:

```yaml
{{- if or .Values.agentConfig.agentsMd .Values.agentConfig.subagentsYaml }}
apiVersion: v1
kind: ConfigMap
metadata:
  name: athena-agent-config
  labels:
    {{- include "athena.labels" . | nindent 4 }}
data:
  {{- if .Values.agentConfig.agentsMd }}
  AGENTS.md: |
    {{- .Values.agentConfig.agentsMd | nindent 4 }}
  {{- end }}
  {{- if .Values.agentConfig.subagentsYaml }}
  subagents.yaml: |
    {{- .Values.agentConfig.subagentsYaml | nindent 4 }}
  {{- end }}
{{- end }}
```

Note: The outer conditional stays because without the deployer role providing content, no ConfigMap should be created (dev/local usage falls back to baked-in files). When the deployer role provides both values, the ConfigMap is always created with both keys.

- [ ] **Step 2: Verify template renders correctly**

Run: `helm template test deploy/helm/athena/ --set-file agentConfig.agentsMd=AGENTS.md --set-file agentConfig.subagentsYaml=subagents.yaml 2>&1 | grep -A5 "kind: ConfigMap"`

Expected: Shows `name: athena-agent-config` with data keys

- [ ] **Step 3: Verify no ConfigMap without values**

Run: `helm template test deploy/helm/athena/ 2>&1 | grep "ConfigMap"`

Expected: No output (ConfigMap not created when values are empty)

- [ ] **Step 4: Commit**

```bash
git add deploy/helm/athena/templates/configmap.yaml
git commit -m "feat(helm): use fixed name athena-agent-config for ConfigMap

Predictable name lets students 'oc edit configmap athena-agent-config'
without needing to know the Helm release name.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: Update Helm Deployment Template

**Files:**
- Modify: `deploy/helm/athena/templates/deployment.yaml:96-121`

- [ ] **Step 1: Update volumeMounts — always mount ConfigMap when present**

Replace lines 96-110 (the `volumeMounts:` block) with:

```yaml
          volumeMounts:
            {{- if .Values.agentConfig.agentsMd }}
            - name: config
              mountPath: /app/AGENTS.md
              subPath: AGENTS.md
              readOnly: true
            {{- end }}
            {{- if .Values.agentConfig.subagentsYaml }}
            - name: config
              mountPath: /app/subagents.yaml
              subPath: subagents.yaml
              readOnly: true
            {{- end }}
            {{- if .Values.skills.persistence.enabled }}
            - name: skills
              mountPath: /app/skills
            {{- end }}
```

Note: `readOnly: true` added to ConfigMap mounts — the ConfigMap is edited via `oc edit configmap`, not from inside the pod.

- [ ] **Step 2: Add initContainer before the containers block**

Insert the initContainer block after `spec:` (line 17) and before `containers:` (line 18). The full `spec:` section becomes:

```yaml
    spec:
      {{- if .Values.skills.persistence.enabled }}
      initContainers:
        - name: init-skills
          image: "{{ .Values.image.repository }}:{{ .Values.image.tag }}"
          imagePullPolicy: {{ .Values.image.pullPolicy }}
          command: ["sh", "-c"]
          args:
            - |
              if [ -z "$(ls -A /mnt/skills 2>/dev/null)" ]; then
                cp -r /app/skills-default/* /mnt/skills/
                echo "Skills initialized from image defaults"
              else
                echo "Skills PVC already populated, skipping"
              fi
          volumeMounts:
            - name: skills
              mountPath: /mnt/skills
      {{- end }}
      containers:
```

- [ ] **Step 3: Update volumes block — use fixed ConfigMap name**

Replace lines 111-121 (the `volumes:` block) with:

```yaml
      volumes:
        {{- if or .Values.agentConfig.agentsMd .Values.agentConfig.subagentsYaml }}
        - name: config
          configMap:
            name: athena-agent-config
        {{- end }}
        {{- if .Values.skills.persistence.enabled }}
        - name: skills
          persistentVolumeClaim:
            claimName: {{ include "athena.fullname" . }}-skills
        {{- end }}
```

- [ ] **Step 4: Verify template renders with all features**

Run: `helm template test deploy/helm/athena/ --set-file agentConfig.agentsMd=AGENTS.md --set-file agentConfig.subagentsYaml=subagents.yaml --set skills.persistence.enabled=true 2>&1 | grep -E "initContainers|init-skills|athena-agent-config|skills-default|mountPath"`

Expected: Shows initContainer with `init-skills`, ConfigMap name `athena-agent-config`, mount paths for AGENTS.md, subagents.yaml, and skills

- [ ] **Step 5: Verify template renders without optional features**

Run: `helm template test deploy/helm/athena/ --set skills.persistence.enabled=false 2>&1 | grep -c "initContainers"`

Expected: `0` (no initContainer when PVC disabled)

- [ ] **Step 6: Commit**

```bash
git add deploy/helm/athena/templates/deployment.yaml
git commit -m "feat(helm): add initContainer for skills PVC pre-population

initContainer copies baked-in skills from /app/skills-default/ to the
PVC on first deploy. Skips if PVC already has content, preserving
student additions across restarts. ConfigMap mounts use fixed name
athena-agent-config and readOnly: true.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: Update Helm values.yaml Comments

**Files:**
- Modify: `deploy/helm/athena/values.yaml:38-50`

- [ ] **Step 1: Update agentConfig and skills comments**

Replace lines 38-50 with:

```yaml
agentConfig:
  opsManagerModel: "openai/claude-sonnet-4-6"
  specialistModel: "openai/claude-sonnet-4-6"
  reviewerModel: "openai/claude-3-5-haiku"
  # AGENTS.md and subagents.yaml content for the athena-agent-config ConfigMap.
  # The deployer role provides these from the cloned repo.
  # For manual helm install: --set-file agentConfig.agentsMd=./AGENTS.md
  agentsMd: ""
  subagentsYaml: ""

skills:
  persistence:
    enabled: true
    size: 1Gi
```

Also update the image repository on line 2 from `quay.io/tonykay/athena-aiops` to `quay.io/rhpds/athena-aiops`:

```yaml
image:
  repository: quay.io/rhpds/athena-aiops
```

- [ ] **Step 2: Commit**

```bash
git add deploy/helm/athena/values.yaml
git commit -m "chore(helm): update values.yaml comments and image repo

Clarify ConfigMap and skills PVC usage. Fix image repo to rhpds org.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 6: Update Deployer Role Helm Values Template

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2:30-39`

- [ ] **Step 1: Add agentConfig content and skills persistence to helm values template**

Replace lines 30-39:

```yaml
agentConfig:
  opsManagerModel: "{{ ocp4_workload_athena_tenant_ops_manager_model }}"
  specialistModel: "{{ ocp4_workload_athena_tenant_specialist_model }}"
  reviewerModel: "{{ ocp4_workload_athena_tenant_reviewer_model }}"
  agentsMd: ""
  subagentsYaml: ""

skills:
  persistence:
    enabled: false
```

With:

```yaml
agentConfig:
  opsManagerModel: "{{ ocp4_workload_athena_tenant_ops_manager_model }}"
  specialistModel: "{{ ocp4_workload_athena_tenant_specialist_model }}"
  reviewerModel: "{{ ocp4_workload_athena_tenant_reviewer_model }}"

skills:
  persistence:
    enabled: true
```

Note: `agentsMd` and `subagentsYaml` are removed from the template — they will be passed via `--set-file` in the Helm deploy task instead. This avoids YAML-in-YAML escaping issues.

- [ ] **Step 2: Update the Helm deploy task in workload.yml to pass config files**

In `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_athena_tenant/tasks/workload.yml`, find the Helm deploy task (the one using `kubernetes.core.helm`) and add `set_values` for the config files. The task currently looks like:

```yaml
- name: Deploy Athena via Helm
  kubernetes.core.helm:
    name: "{{ ocp4_workload_athena_tenant_release_name }}"
    chart_ref: "/tmp/athena-helm/{{ ocp4_workload_athena_tenant_helm_chart_path }}"
    release_namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
    values_files:
      - /tmp/athena-helm-values.yaml
    state: present
    wait: false
```

Update it to also pass the config files via `values`:

```yaml
- name: Deploy Athena via Helm
  kubernetes.core.helm:
    name: "{{ ocp4_workload_athena_tenant_release_name }}"
    chart_ref: "/tmp/athena-helm/{{ ocp4_workload_athena_tenant_helm_chart_path }}"
    release_namespace: "{{ ocp4_workload_athena_tenant_namespace }}"
    values_files:
      - /tmp/athena-helm-values.yaml
    values:
      agentConfig:
        agentsMd: "{{ lookup('file', '/tmp/athena-helm/AGENTS.md') }}"
        subagentsYaml: "{{ lookup('file', '/tmp/athena-helm/subagents.yaml') }}"
    state: present
    wait: false
```

This reads `AGENTS.md` and `subagents.yaml` from the cloned repo (already available at `/tmp/athena-helm/`) and passes them as Helm values. The `values:` dict merges with `values_files:`.

- [ ] **Step 3: Verify the lookup paths exist in the cloned repo**

Check that the Helm deploy task runs after the git clone task, and that the clone destination (`/tmp/athena-helm/`) contains both `AGENTS.md` and `subagents.yaml` at the repo root.

Run a quick sanity check against the current repo:

```bash
ls -la /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent/AGENTS.md /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent/subagents.yaml
```

Expected: Both files exist at the repo root

- [ ] **Step 4: Commit (in the deepagents-aiops collection repo)**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/templates/helm-values.yaml.j2
git add roles/ocp4_workload_athena_tenant/tasks/workload.yml
git commit -m "feat(athena): externalize agent config via ConfigMap and skills via PVC

- Pass AGENTS.md and subagents.yaml as Helm values from cloned repo
- Enable skills PVC persistence (initContainer pre-populates from image)
- Students can oc edit configmap athena-agent-config to add subagents
- Students can oc cp new skills onto the PVC

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: Build, Push, and Verify

**Files:**
- No file changes — integration verification

- [ ] **Step 1: Run linter and tests**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest tests/ -q
```

Expected: All checks pass, all tests pass

- [ ] **Step 2: Build amd64 image**

```bash
podman build --platform linux/amd64 -t quay.io/rhpds/athena-aiops:latest .
```

Expected: Build succeeds

- [ ] **Step 3: Verify skills-default in built image**

```bash
podman run --rm quay.io/rhpds/athena-aiops:latest ls /app/skills-default/
```

Expected: Shows skill directories (analyze-ansible-failure, analyze-linux-failure, etc.)

- [ ] **Step 4: Push image**

```bash
podman push quay.io/rhpds/athena-aiops:latest
```

Expected: Push succeeds

- [ ] **Step 5: Push both repos**

```bash
# Athena repo
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
git push

# Collection repo
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git push
```

Expected: Both pushes succeed

- [ ] **Step 6: Verify on cluster (manual)**

After the next AgnosticV deployment, verify:

```bash
# ConfigMap exists with both keys
oc get configmap athena-agent-config -o yaml | head -20

# Skills PVC exists and is populated
oc exec deployment/athena -- ls /app/skills/

# ConfigMap is editable
oc edit configmap athena-agent-config
# (verify subagents.yaml content appears in editor)
```
