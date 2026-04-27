# Module 3 Pre-warm + Domain Awareness Fix Design

**Goal:** Replace the ping seed job with job 10 so students arrive at Module 3 with the `sre_linux` "before" ticket already in Kira, saving one wait cycle. Simultaneously fix Module 3 to patch `AGENTS.md` Domain Awareness so `sre_package_management` routing actually works after the student adds the agent.

**Architecture:** Three-part change — provisioner default, a new Gitea config file, and showroom content updates. The Athena image is NOT rebuilt; it retains the old `AGENTS.md` (where `sre_linux` handles packages) so the pre-warmed ticket correctly routes to `sre_linux` as the "before" baseline.

**Tech Stack:** Ansible (provisioner role), AsciiDoc (showroom), YAML (Gitea configs), `oc` CLI (student ConfigMap patch commands)

---

## Background

Module 3 teaches students to add `sre_package_management` by showing a "before" ticket (handled by `sre_linux`) and an "after" ticket (handled by `sre_package_management`). Currently students must launch "10 Install Python 3.14" twice and wait 1–3 minutes each time.

Two bugs exist:
1. **Wait time:** Students wait twice for the same job; the first wait is wasted since the "before" ticket can be pre-provisioned.
2. **Domain Awareness gap:** Module 3 only patches `subagents.yaml` — but `ops_manager` routes via `AGENTS.md` Domain Awareness, not just agent descriptions. After the student adds `sre_package_management` to `subagents.yaml`, Exercise 5 still routes to `sre_linux` because `AGENTS.md` hasn't been updated. The "after" ticket never demonstrates the improvement.

---

## Part 1: Provisioner change

**File:** `deepagents-aiops/roles/ocp4_workload_athena_tenant/defaults/main.yml`

Change one default:
```yaml
# Before
ocp4_workload_athena_tenant_seed_job_name: "02 Ping RHEL Admin"

# After
ocp4_workload_athena_tenant_seed_job_name: "10 Install Python 3.14"
```

Job 10 fails fast (package not found on RHEL — same quick failure as the ping job). The deployed Athena image has the old `AGENTS.md` where `sre_linux` handles package management, so the pre-warmed ticket routes to `sre_linux`. This is exactly the "before" baseline Module 3 needs.

The fire-and-forget mechanism (existing `block:` in `workload.yml` step 12) is unchanged.

---

## Part 2: New Gitea config file

**File:** `agentic-aiops-plays/configs/agents-with-sre-package-mgmt.md`

The updated `AGENTS.md` content — identical to `athena-aiops-deep-agent/AGENTS.md` as it stands today (already updated in the previous session). Domain Awareness section:

```markdown
- **sre_linux**: Systemd services, SELinux, filesystem/permissions (NOT package manager or Satellite — those go to sre_package_management if available)
- **sre_package_management**: DNF/YUM errors, missing or disabled repositories, Satellite content gaps, CRB/EPEL requirements (when available)
```

Students download this file in Module 3 Step 3d and include it in the ConfigMap patch alongside `subagents.yaml`.

This file must be pushed to all Gitea tenant repos (same mechanism used for `subagents-with-sre-package-mgmt.yaml`).

---

## Part 3: Showroom content changes

### 3a. Module 1 — minor text fix

**File:** `showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/03-module-01-problem-domain.adoc`

Change: "9 numbered job templates — `01 Ping RHEL VM` through `09 System Health Check`"
To: "10 numbered job templates — `01 Ping RHEL VM` through `10 Install Python 3.14`"

### 3b. Module 3 — Exercise 1 rewrite

**File:** `showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/05-module-03-first-agent.adoc`

**Exercise 1, Step 1** — Remove "Launch job 10 and wait." Replace with:

> Before you even logged in, job `10 Install Python 3.14` ran automatically during provisioning. Check Kira — the ticket is already there.

The student navigates to Kira and reads the pre-existing `sre_linux` ticket. The content explaining what the ticket lacks (no Satellite context, no SOP, no EPEL/CRB awareness) stays unchanged.

**Step 2** adjusts from "Wait 1–3 minutes" to "Open the existing ticket" — same learning outcome, no wait.

### 3c. Module 3 — Step 3d ConfigMap patch expansion

**Exercise 4, Step 3d** currently downloads only `subagents.yaml` and preserves the existing `AGENTS.md` by reading it from the ConfigMap. Change to also download the updated `AGENTS.md` and include it in the patch.

Add before the ConfigMap patch command:
```bash
curl -sL {gitea_url}/{user}/agentic-devops-plays/raw/branch/main/configs/agents-with-sre-package-mgmt.md \
  -o /tmp/agents-new.md
```

Update the `oc create configmap` command from:
```bash
oc create configmap athena-agent-config \
  --from-file=subagents.yaml=/tmp/subagents-new.yaml \
  --from-file=AGENTS.md=<(oc get configmap athena-agent-config -o jsonpath='{.data.AGENTS\.md}') \
  --dry-run=client -o yaml | oc apply -f -
```
To:
```bash
oc create configmap athena-agent-config \
  --from-file=subagents.yaml=/tmp/subagents-new.yaml \
  --from-file=AGENTS.md=/tmp/agents-new.md \
  --dry-run=client -o yaml | oc apply -f -
```

Add a verification step after the existing subagents.yaml verify:
```bash
oc get configmap athena-agent-config -o jsonpath='{.data.AGENTS\.md}' | grep -A2 "sre_package_management"
```
Expected output:
```
- **sre_package_management**: DNF/YUM errors, missing or disabled repositories, Satellite content gaps, CRB/EPEL requirements (when available)
```

---

## What does NOT change

- Athena image and its embedded `AGENTS.md` (keep old routing — required for pre-warm to produce `sre_linux` ticket)
- Module 2 content
- Module 3 Exercises 2–4 structure (other than the ConfigMap patch command in 3d)
- Module 3 Exercise 5 (student still launches job 10 once — one wait cycle)
- Module 3 Exercise 6 comparison table
- `subagents-with-sre-package-mgmt.yaml` in configs (already correct)

---

## Module 3 flow after this change

| Step | Before | After |
|------|--------|-------|
| Arrive at Module 3 | 0 tickets for job 10 | 1 pre-warmed ticket (`sre_linux`) |
| Exercise 1 | Launch job 10, wait 1–3 min | Read pre-existing ticket |
| Exercise 4, Step 3d | Patch `subagents.yaml` only | Patch `subagents.yaml` + `AGENTS.md` |
| Exercise 5 | Launch job 10, wait 1–3 min | Same — one wait cycle |
| Exercise 6 | Compare 2 tickets | Same comparison, same outcome |

**Wait cycles saved:** 1 (from ~2 down to ~1 per student)
