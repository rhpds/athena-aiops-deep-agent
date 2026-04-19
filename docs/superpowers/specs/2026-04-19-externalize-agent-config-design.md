# Externalize Agent Config and Skills for Runtime Customization

**Date:** 2026-04-19
**Status:** Draft
**Author:** Tony Kay + Claude

## Problem

Athena's agent configuration (`AGENTS.md`, `subagents.yaml`) and skills (`skills/`) are baked into the container image. Students in the AIOps lab cannot add new subagents or skills without rebuilding the image. A key lab exercise requires students to add a new SRE subagent via `oc edit configmap` and mount new skills onto the running deployment.

## Design

### ConfigMap: `athena-agent-config`

A ConfigMap named `athena-agent-config` holds `AGENTS.md` and `subagents.yaml`. It is always created and always mounted — there is no "fall back to baked-in" mode.

**Pre-population:** The Ansible deployer role populates the ConfigMap with the current content of `AGENTS.md` and `subagents.yaml` from the Athena repo at deploy time via `--set-file` or inline in the Helm values template.

**Mount paths:**
- `/app/AGENTS.md` (subPath: `AGENTS.md`)
- `/app/subagents.yaml` (subPath: `subagents.yaml`)

**Student workflow:**
```bash
oc edit configmap athena-agent-config
# Add new subagent definition to subagents.yaml
# Optionally update AGENTS.md domain awareness section
oc rollout restart deployment/athena
```

### PVC: Skills Volume

A 1Gi PersistentVolumeClaim provides the `/app/skills/` directory. Enabled by default.

**Pre-population via initContainer:** An initContainer runs on every pod start. It checks whether the PVC is empty (no files). If empty, it copies the baked-in skills from the image (`/app/skills-default/`) to the PVC mount (`/app/skills/`). If the PVC already has content, the initContainer exits without modifying it. This preserves student additions across pod restarts.

**Image build change:** The Dockerfile copies skills to two locations:
- `/app/skills-default/` — read-only reference copy, never mounted over
- `/app/skills/` — default location, overridden by PVC mount at runtime

**initContainer spec:**
```yaml
initContainers:
  - name: init-skills
    image: {{ .Values.image.repository }}:{{ .Values.image.tag }}
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
```

**Student workflow:**
```bash
# Option A: copy a tarball
oc cp new-skills.tar.gz <pod>:/tmp/
oc exec <pod> -- tar xzf /tmp/new-skills.tar.gz -C /app/skills/

# Option B: copy a directory
oc cp my-new-skill/ <pod>:/app/skills/my-new-skill/

# Then update subagents.yaml to reference the new skill path
oc edit configmap athena-agent-config
oc rollout restart deployment/athena
```

### Model Names

Drop the `openai:` prefix from `subagents.yaml`. Use bare MaaS model names (e.g., `claude-sonnet-4-6` instead of `openai:claude-sonnet-4-6`). The parser in `pipeline.py` already handles both formats — it splits on `:` if present — so this is backwards compatible.

MaaS model names match the `/v1/models` endpoint output exactly. No provider prefix is needed because `ChatOpenAI` always uses the OpenAI-compatible API regardless.

### Rollout Behavior

In-progress agent pipelines are lost when a rollout restarts the pod. FastAPI `BackgroundTasks` run in-process; when the old pod receives `SIGTERM`, in-flight analyses are killed after the termination grace period.

This is an accepted limitation for the lab context:
- Low volume (students run 1-3 jobs at a time)
- Jobs can be re-launched from AAP2
- Showroom instructions will advise waiting for analysis completion before rolling out

## Changes Required

### Helm Chart (`deploy/helm/athena/`)

**`templates/configmap.yaml`:**
- Remove conditional creation — ConfigMap is always created
- Always include `AGENTS.md` and `subagents.yaml` data keys
- Fixed name: `athena-agent-config`

**`templates/deployment.yaml`:**
- Remove conditional on ConfigMap volume mounts — always mount both files
- Add initContainer `init-skills` for PVC pre-population
- Skills PVC volume mount remains conditional on `skills.persistence.enabled`

**`templates/pvc.yaml`:**
- No change (already exists with conditional on `skills.persistence.enabled`)

**`values.yaml`:**
- `agentConfig.agentsMd`: empty default (deployer role provides content)
- `agentConfig.subagentsYaml`: empty default (deployer role provides content)
- `skills.persistence.enabled`: `true` (already default)
- For manual `helm install` without the deployer role, use `--set-file agentConfig.agentsMd=./AGENTS.md`

### Dockerfile

- Add `COPY skills/ skills-default/` to create the read-only reference copy
- Keep existing `COPY skills/ skills/` for non-PVC fallback (development)

### Deployer Role (`ocp4_workload_athena_tenant`)

**`templates/helm-values.yaml.j2`:**
- Set `agentConfig.agentsMd` and `agentConfig.subagentsYaml` with the file contents (via `lookup('file', ...)` or inline)
- Set `skills.persistence.enabled: true`

### `subagents.yaml`

- Remove `openai:` prefix from all model values
- `openai:claude-sonnet-4-6` becomes `claude-sonnet-4-6`
- `openai:claude-3-5-haiku` becomes `claude-3-5-haiku`

### `pipeline.py`

- No functional change needed — parser handles both formats
- Consider removing the prefix-stripping code in a future cleanup if the prefix convention is fully deprecated

## ConfigMap Name

Fixed name: `athena-agent-config`. ConfigMaps are namespace-scoped, so this does not conflict across tenants. The fixed name makes lab instructions predictable.

## Out of Scope

- Persistent job queue for surviving rollouts (future enhancement if needed)
- Specific subagent content for the lab exercise (defined in showroom repo)
- Hot-reloading of config without restart (Deep Agents loads config at agent creation time)
