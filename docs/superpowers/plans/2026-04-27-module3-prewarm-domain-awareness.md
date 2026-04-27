# Module 3 Pre-warm + Domain Awareness Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the ping seed job with job 10 so Module 3 students arrive with an `sre_linux` "before" ticket already in Kira, and fix Module 3 to also patch `AGENTS.md` so `sre_package_management` routing actually works.

**Architecture:** Four independent changes across four repos: (1) commit pending AGENTS.md to athena-aiops-deep-agent, (2) create a new config file in agentic-aiops-plays, (3) one-line provisioner change in deepagents-aiops, (4) showroom content edits. No code changes — all config, YAML, and AsciiDoc.

**Tech Stack:** Git, Ansible YAML defaults, AsciiDoc (showroom), Bash (oc commands inside lab content)

---

## File Map

| File | Repo | Change |
|------|------|--------|
| `AGENTS.md` | `athena-aiops-deep-agent` | Commit + push (already edited, just staged/pushed) |
| `configs/agents-with-sre-package-mgmt.md` | `agentic-aiops-plays` | Create — copy of updated AGENTS.md |
| `roles/ocp4_workload_athena_tenant/defaults/main.yml:54` | `deepagents-aiops` | Change seed job name |
| `content/modules/ROOT/pages/03-module-01-problem-domain.adoc:40` | `showroom` | "9 → 10 templates" text fix |
| `content/modules/ROOT/pages/05-module-03-first-agent.adoc:69-108` | `showroom` | Exercise 1 rewrite (pre-existing ticket) |
| `content/modules/ROOT/pages/05-module-03-first-agent.adoc:341-452` | `showroom` | Step 3d: add AGENTS.md download + patch + verify |

---

## Task 1: Commit and push pending AGENTS.md

`AGENTS.md` in `athena-aiops-deep-agent` was updated last session (added `sre_package_management` to Domain Awareness, narrowed `sre_linux`) but never committed or pushed.

**Files:**
- Modify (commit): `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent/AGENTS.md`

- [ ] **Step 1: Verify the current diff**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent
git diff AGENTS.md
```

Expected: diff showing `sre_linux` narrowed and `sre_package_management` added to Domain Awareness:
```
-  **sre_linux**: Systemd services, SELinux, filesystem/permissions, package manager (dnf/yum)...
+  **sre_linux**: Systemd services, SELinux, filesystem/permissions (NOT package manager or Satellite — those go to sre_package_management if available)
+  **sre_package_management**: DNF/YUM errors, missing or disabled repositories, Satellite content gaps, CRB/EPEL requirements (when available)
```

- [ ] **Step 2: Stage and commit**

```bash
git add AGENTS.md
git commit -m "fix: add sre_package_management to Domain Awareness, narrow sre_linux"
```

Expected:
```
[main xxxxxxx] fix: add sre_package_management to Domain Awareness, narrow sre_linux
 1 file changed, 3 insertions(+), 2 deletions(-)
```

- [ ] **Step 3: Push to GitHub**

```bash
git push
```

Expected:
```
To github.com:rhpds/athena-aiops-deep-agent.git (or similar)
   xxxxxxx..yyyyyyy  main -> main
```

---

## Task 2: Create agents-with-sre-package-mgmt.md in agentic-aiops-plays

Students download this file in Module 3 Step 3d to update `AGENTS.md` in their ConfigMap. Content is identical to the now-committed `athena-aiops-deep-agent/AGENTS.md`.

**Files:**
- Create: `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/configs/agents-with-sre-package-mgmt.md`

- [ ] **Step 1: Copy AGENTS.md as the new config file**

```bash
cp /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent/AGENTS.md \
   /Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/configs/agents-with-sre-package-mgmt.md
```

- [ ] **Step 2: Verify the file contains sre_package_management**

```bash
grep -A2 "sre_package_management" /Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/configs/agents-with-sre-package-mgmt.md
```

Expected:
```
- **sre_package_management**: DNF/YUM errors, missing or disabled repositories, Satellite content gaps, CRB/EPEL requirements (when available)
```

- [ ] **Step 3: Verify sre_linux is narrowed (no package manager)**

```bash
grep "sre_linux" /Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/configs/agents-with-sre-package-mgmt.md
```

Expected:
```
- **sre_linux**: Systemd services, SELinux, filesystem/permissions (NOT package manager or Satellite — those go to sre_package_management if available)
```

- [ ] **Step 4: Commit and push**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays
git add configs/agents-with-sre-package-mgmt.md
git commit -m "feat: add agents-with-sre-package-mgmt.md for Module 3 ConfigMap patch"
git push
```

Expected:
```
[main xxxxxxx] feat: add agents-with-sre-package-mgmt.md for Module 3 ConfigMap patch
 1 file changed, 64 insertions(+)
 create mode 100644 configs/agents-with-sre-package-mgmt.md
To github.com:rhpds/agentic-aiops-plays.git
   xxxxxxx..yyyyyyy  main -> main
```

---

## Task 3: Change provisioner seed job

One-line change in the Ansible role defaults.

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_athena_tenant/defaults/main.yml:54`

- [ ] **Step 1: Make the change**

In `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_athena_tenant/defaults/main.yml`, change line 54 from:

```yaml
ocp4_workload_athena_tenant_seed_job_name: "02 Ping RHEL Admin"
```

To:

```yaml
ocp4_workload_athena_tenant_seed_job_name: "10 Install Python 3.14"
```

- [ ] **Step 2: Verify the change**

```bash
grep "seed_job_name" /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops/roles/ocp4_workload_athena_tenant/defaults/main.yml
```

Expected:
```
ocp4_workload_athena_tenant_seed_job_name: "10 Install Python 3.14"
```

- [ ] **Step 3: Commit and push**

```bash
cd /Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops
git add roles/ocp4_workload_athena_tenant/defaults/main.yml
git commit -m "fix: seed job 10 Install Python 3.14 instead of 02 Ping RHEL Admin"
git push
```

Expected:
```
[main xxxxxxx] fix: seed job 10 Install Python 3.14 instead of 02 Ping RHEL Admin
 1 file changed, 1 insertion(+), 1 deletion(-)
```

---

## Task 4: Module 1 template count text fix

The Module 1 tour text says "9 numbered job templates" — now there are 10.

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/03-module-01-problem-domain.adoc:40`

- [ ] **Step 1: Make the change**

In `03-module-01-problem-domain.adoc` line 40, change:

```
You'll see 9 numbered job templates — `01 Ping RHEL VM` through `09 System Health Check`. These represent the day-to-day automation that Meridian's SRE team runs against their infrastructure: health checks, package updates, application deployments, and compliance scans.
```

To:

```
You'll see 10 numbered job templates — `01 Ping RHEL VM` through `10 Install Python 3.14`. These represent the day-to-day automation that Meridian's SRE team runs against their infrastructure: health checks, package updates, application deployments, and compliance scans.
```

- [ ] **Step 2: Verify**

```bash
grep "numbered job templates" /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/03-module-01-problem-domain.adoc
```

Expected:
```
You'll see 10 numbered job templates — `01 Ping RHEL VM` through `10 Install Python 3.14`.
```

- [ ] **Step 3: Commit**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops
git add content/modules/ROOT/pages/03-module-01-problem-domain.adoc
git commit -m "fix: update template count 9 -> 10 in Module 1"
```

---

## Task 5: Module 3 Exercise 1 rewrite (pre-existing ticket)

Students no longer launch job 10 in Exercise 1 — it already ran during provisioning. Replace the "launch and wait" steps with "open the existing ticket."

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/05-module-03-first-agent.adoc:69-108`

- [ ] **Step 1: Replace Exercise 1 (lines 69–108)**

Replace the entire block from `== Exercise 1: Launch the job and see the gap` through `This is the gap a specialist agent closes. Let's build one.` with:

```asciidoc
== Exercise 1: See the gap

The AI/ML team at Meridian Financial has requested Python 3.14 on their RHEL servers. This job ran automatically when your environment was provisioned — so the ticket is already waiting for you in Kira.

The job failed with this error:

----
TASK [Install Python 3.14] ***
fatal: [rhel-node-01]: FAILED! => {"changed": false,
  "failures": ["No match for argument: python3.14"],
  "msg": "Failed to install some of the specified packages",
  "rc": 1, "results": []}
----

=== Step 1: Read the Kira ticket

. In the **Kira** tab (log in with `{user}` / `{password}` if prompted), find the open ticket for **10 Install Python 3.14**

. Read the ticket carefully. Notice what it **doesn't** contain:
+
--
* No mention of Meridian Financial's Satellite servers or the specific content view model used by different teams
* No reference to the Content View Request SOP (Meridian Standard Operating Procedure v2.3)
* No awareness that the AI/ML team needs CRB (CodeReady Builder) and EPEL to be enabled in their content view
* No suggestion of the `#platform-satellite` fast-track escalation path
--
+
`sre_linux` gave a generic "check your package manager and repositories" answer. Technically accurate — but useless to anyone at Meridian. It doesn't know how your organization works.
+
This is the gap a specialist agent closes. Let's build one.
```

- [ ] **Step 2: Verify Exercise 1 heading and no launch step remains**

```bash
grep -n "Exercise 1\|Launch.*10\|Launch.*Python\|rocket icon\|Watch the job fail\|Wait 1-3 minutes" \
  /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/05-module-03-first-agent.adoc | head -10
```

Expected: Only Exercise 1 heading appears. No lines containing "Launch" for job 10, "rocket icon", "Watch the job fail", or "Wait 1-3 minutes" in the Exercise 1 area. (Exercise 5 still has a launch step — that's correct.)

- [ ] **Step 3: Commit**

```bash
git add content/modules/ROOT/pages/05-module-03-first-agent.adoc
git commit -m "fix: Module 3 Exercise 1 uses pre-warmed ticket instead of launching job"
```

---

## Task 6: Module 3 Step 3d — add AGENTS.md download, update patch command, add verify

Step 3d currently patches only `subagents.yaml` and preserves `AGENTS.md` by reading it from the existing ConfigMap. Change it to also download the updated `AGENTS.md` from Gitea and include it in the patch. Add a verification step.

**Files:**
- Modify: `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/05-module-03-first-agent.adoc`

The section to change starts at `=== Step 3d: Patch the ConfigMap` (currently around line 370 — line numbers will shift after Task 5's edit).

- [ ] **Step 1: Add AGENTS.md download before the ConfigMap patch command**

Find this block in Step 3d (starts after the `subagents.yaml` verify steps):

```asciidoc
=== Step 3d: Patch the ConfigMap

. Apply the new `subagents.yaml` to the ConfigMap:
+
[source,bash,role="execute",subs=attributes+]
----
oc create configmap athena-agent-config \
  --from-file=subagents.yaml=/tmp/subagents-new.yaml \
  --from-file=AGENTS.md=<(oc get configmap athena-agent-config -o jsonpath='{.data.AGENTS\.md}') \
  --dry-run=client -o yaml | oc apply -f -
----
+
_Expected output:_
+
----
configmap/athena-agent-config configured
----
+
NOTE: You may see a Warning about a missing `kubectl.kubernetes.io/last-applied-configuration` annotation — this is safe to ignore. It only appears the first time because the ConfigMap was originally created by Helm, not `oc apply`
+
This command creates a new ConfigMap definition from the downloaded file (preserving the existing `AGENTS.md`), generates the YAML with `--dry-run=client`, and pipes it to `oc apply` which updates the ConfigMap in place.
```

Replace it with:

```asciidoc
=== Step 3d: Patch the ConfigMap

You need to update two keys in the ConfigMap: `subagents.yaml` (to add the new agent) and `AGENTS.md` (to update `ops_manager`'s routing rules so it knows to delegate package failures to `sre_package_management` instead of `sre_linux`).

. Download the updated `ops_manager` routing rules:
+
[source,bash,role="execute",subs=attributes+]
----
curl -sL {gitea_url}/{user}/agentic-devops-plays/raw/branch/main/configs/agents-with-sre-package-mgmt.md \
  -o /tmp/agents-new.md
----

. Verify the routing update — confirm `sre_package_management` appears in Domain Awareness:
+
[source,bash,role="execute",subs=attributes+]
----
grep "sre_package_management\|sre_linux" /tmp/agents-new.md
----
+
_Expected output:_
+
----
- **sre_linux**: Systemd services, SELinux, filesystem/permissions (NOT package manager or Satellite — those go to sre_package_management if available)
- **sre_package_management**: DNF/YUM errors, missing or disabled repositories, Satellite content gaps, CRB/EPEL requirements (when available)
----

. Apply both files to the ConfigMap in one command:
+
[source,bash,role="execute",subs=attributes+]
----
oc create configmap athena-agent-config \
  --from-file=subagents.yaml=/tmp/subagents-new.yaml \
  --from-file=AGENTS.md=/tmp/agents-new.md \
  --dry-run=client -o yaml | oc apply -f -
----
+
_Expected output:_
+
----
configmap/athena-agent-config configured
----
+
NOTE: You may see a Warning about a missing `kubectl.kubernetes.io/last-applied-configuration` annotation — this is safe to ignore. It only appears the first time because the ConfigMap was originally created by Helm, not `oc apply`
+
This command rebuilds the ConfigMap from both downloaded files and applies it in place. Both `subagents.yaml` (new agent definition) and `AGENTS.md` (updated routing rules) are replaced in one atomic apply.
```

- [ ] **Step 2: Add AGENTS.md verification step after the subagents.yaml verify**

Find this block (the existing subagents.yaml verify at the end of the Verify section):

```asciidoc
. Confirm `sre_package_management` is in the ConfigMap:
+
[source,bash,role="execute",subs=attributes+]
----
oc get configmap athena-agent-config -o jsonpath='{.data.subagents\.yaml}' | grep -A3 "sre_package_management"
----
+
_Expected output:_
+
----
sre_package_management:
  description: >
    Package management specialist. Delegate all package installation failures:
    dnf/yum errors, missing packages, Satellite content view gaps, EPEL/CRB
----
```

After that block, add:

```asciidoc
. Confirm `ops_manager` routing rules include `sre_package_management`:
+
[source,bash,role="execute",subs=attributes+]
----
oc get configmap athena-agent-config -o jsonpath='{.data.AGENTS\.md}' | grep "sre_package_management\|sre_linux"
----
+
_Expected output:_
+
----
- **sre_linux**: Systemd services, SELinux, filesystem/permissions (NOT package manager or Satellite — those go to sre_package_management if available)
- **sre_package_management**: DNF/YUM errors, missing or disabled repositories, Satellite content gaps, CRB/EPEL requirements (when available)
----
+
Both the agent definition (`subagents.yaml`) and the routing rules (`AGENTS.md`) are now updated. The `ops_manager` will route package management failures to `sre_package_management` instead of `sre_linux`.
```

- [ ] **Step 3: Verify Step 3d contains both downloads**

```bash
grep -n "agents-new.md\|agents-with-sre-package-mgmt\|AGENTS\.md" \
  /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/05-module-03-first-agent.adoc
```

Expected: Lines for the `curl` download of `agents-with-sre-package-mgmt.md`, the `/tmp/agents-new.md` output path, the `--from-file=AGENTS.md=/tmp/agents-new.md` patch argument, and the `jsonpath='{.data.AGENTS\.md}'` verify command.

- [ ] **Step 4: Verify the old process-substitution syntax is gone**

```bash
grep "AGENTS.md=<(" \
  /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/05-module-03-first-agent.adoc
```

Expected: no output (the `<(oc get configmap ...)` process substitution is fully replaced).

- [ ] **Step 5: Commit**

```bash
git add content/modules/ROOT/pages/05-module-03-first-agent.adoc
git commit -m "fix: Module 3 Step 3d patches AGENTS.md + subagents.yaml for sre_package_management routing"
```

---

## Task 7: Push showroom and verify

- [ ] **Step 1: Push showroom**

```bash
cd /Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops
git push
```

Expected:
```
To github.com:rhpds/showroom-summit-2026-lb2465-agentic-ai-ops.git (or similar)
   xxxxxxx..yyyyyyy  main -> main
```

- [ ] **Step 2: Confirm all four repos are clean**

```bash
for repo in \
  "/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent" \
  "/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays" \
  "/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops" \
  "/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/showroom-summit-2026-lb2465-agentic-ai-ops"; do
  echo "=== $repo ==="
  git -C "$repo" status --short
done
```

Expected: Each repo shows either nothing (clean) or only unrelated untracked files. No modified tracked files.

---

## Self-review

**Spec coverage:**
- Part 1 (provisioner): Task 3 ✓
- Part 2 (new Gitea config): Tasks 1 + 2 ✓ (Task 1 commits AGENTS.md source, Task 2 copies it)
- Part 3a (Module 1 text): Task 4 ✓
- Part 3b (Module 3 Exercise 1 rewrite): Task 5 ✓
- Part 3c (Step 3d expansion + verify): Task 6 ✓
- Push all repos: Task 7 ✓

**Placeholder scan:** None found.

**Type consistency:** File paths consistent across all tasks. `agents-with-sre-package-mgmt.md` named consistently in Tasks 2 and 6. ConfigMap key `AGENTS.md` named consistently in Tasks 6.
