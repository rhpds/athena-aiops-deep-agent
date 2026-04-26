# Module 3: sre_package_management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Module 3 sre_ssh exercise with a new sre_package_management agent that handles Python 3.14 DNF failures, demonstrating before/after routing quality using the same job.

**Architecture:** Four parallel repo changes (Athena skill, plays configs, deepagents-aiops job template, showroom content) followed by image rebuild and Gitea sync. All changes are additive — base subagents.yaml untouched, sre_linux narrowing only in pre-built Module 3 config.

**Tech Stack:** Python/YAML (Athena/subagents), Ansible/Jinja2 (deepagents-aiops role), AsciiDoc (showroom), Gitea API, AAP2 API, podman multi-arch build.

---

## File Map

| Repo | File | Action |
|------|------|--------|
| `athena-aiops-deep-agent` | `skills/analyze-package-management/SKILL.md` | Create |
| `agentic-aiops-plays` | `playbooks/install-python314.yml` | Create |
| `agentic-aiops-plays` | `configs/subagents-with-sre-package-mgmt.yaml` | Create |
| `agentic-aiops-plays` | `configs/analyze-package-management-SKILL.md` | Create |
| `agentic-aiops-plays` | `configs/subagents-oss-models.yaml` | Modify |
| `deepagents-aiops` | `roles/ocp4_workload_aap2_tenant_config/defaults/main.yml` | Modify |
| `deepagents-aiops` | `roles/ocp4_workload_aap2_tenant_config/tasks/` | Modify (if template list is in tasks) |
| `agentic-aiops-showroom` | `content/modules/ROOT/pages/05-module-03-first-agent.adoc` | Modify |

---

## Task 1: Create analyze-package-management skill (Athena repo)

**Repo:** `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent`

**Files:**
- Create: `skills/analyze-package-management/SKILL.md`

- [ ] Create skill directory and SKILL.md

```bash
mkdir -p skills/analyze-package-management
```

Write `skills/analyze-package-management/SKILL.md`:

```markdown
# analyze-package-management

You are analyzing a package management failure on a Red Hat Enterprise Linux host
managed by Meridian Financial's Ansible Automation Platform.

## Your Task

Perform root-cause analysis on the package installation failure. Identify the exact
cause (missing repo, disabled content view, CRB/EPEL requirement) and recommend the
specific SOP action.

## Diagnostic Workflow

1. Read `incident.json` — identify the exact package name and the DNF error string
2. Classify the error:
   - `No match for argument: <package>` → package absent from all enabled repos/content views
   - `Repository 'X' is disabled` → repo exists in Satellite but not enabled in this host's activation key
   - `Failed to download metadata for repo` → Satellite reachability or content sync issue
   - `No module streams match` → AppStream module stream not enabled or conflicting stream active
3. Determine whether the package requires CRB, EPEL, or a custom Satellite content view
4. Select the appropriate SOP path below

## Meridian Financial Satellite Infrastructure

Meridian Financial operates two HA Satellite 6 servers:

- **Primary:** `satellite-primary.meridian.internal` (London DC)
- **Replica:** `satellite-replica.meridian.internal` (Dublin DC)

Both servers are always active and replicated. If a package is unavailable, the root
cause is almost never Satellite availability — suspect content view or activation key
configuration first.

### Lifecycle Environments

Content flows through three lifecycle environments:

```
Dev → QA → Prod
```

Content must be explicitly promoted at each stage. A package published to Dev is not
automatically available in QA or Prod.

### Content View Architecture

Content views are **per-team, per-project** — not global. Key content views:

- `cv-platform-rhel9` — Platform team (includes CRB, internal tooling)
- `cv-security-rhel9` — Security team (includes CRB, SCAP tools)
- `cv-base-rhel9` — Default for most RHEL VMs (no CRB, no EPEL)
- `cv-aiml-rhel9` — AI/ML project (to be created — see SOP below)

**CRB note:** CodeReady Builder is included in `cv-platform-rhel9` and
`cv-security-rhel9` but **not** in `cv-base-rhel9`. Most RHEL VMs are registered
to `cv-base-rhel9`, which is why packages requiring CRB (like `python3.14`) fail.

**EPEL note:** EPEL is mirrored internally at `satellite-primary.meridian.internal`
but must be explicitly added to a content view — it is not in `cv-base-rhel9` by default.

## Common Failure Patterns

| DNF Error | Root Cause | Required Action |
|-----------|-----------|----------------|
| `No match for argument: python3.14` | Not in `cv-base-rhel9`; requires CRB + EPEL | Request new content view with CRB + EPEL (SOP v2.3) |
| `Repository 'epel' is disabled` | EPEL not in activation key | Request content view update to include internal EPEL mirror |
| `No match for argument: <pkg>` (CRB needed) | CRB not in current content view | Include CRB flag in content view request |
| Package available in Dev but not Prod | Content view promoted to Dev only | Request promotion to target lifecycle environment |
| `Failed to download metadata` | Satellite sync issue or network | Check Satellite sync status; retry against primary if replica lag |

## Standard Operating Procedures

### SOP v2.3 — New Content View Request

For packages not available in the current content view:

1. Raise a ticket to the Platform team queue with title: **"New Content View Request — [project name]"**
2. Required fields:
   - Project name and team
   - Target lifecycle environment (Dev / QA / Prod)
   - Package list (include exact package names)
   - Additional repo requirements: CRB required? EPEL required?
   - Business justification
3. Standard SLA: **2 business days**
4. For Python 3.14 specifically: flag that CRB (`rhel-9-for-x86_64-crb-rpms`) and
   EPEL are both required — Platform team will create `cv-aiml-rhel9` with these repos

### Fast-Track Escalation (production-blocking only)

1. Post in `#platform-satellite` Slack channel with manager approval tag
2. Reference the ticket number from the standard SOP v2.3 request
3. SLA: **4 hours during business hours**

### Self-Service (Dev lifecycle only)

For immediate unblocking on Dev hosts only (not permitted in QA or Prod):

```bash
# Enable CRB repo directly on the host
subscription-manager repos --enable codeready-builder-for-rhel-9-x86_64-rpms

# Then install the package
dnf install python3.14
```

This is a temporary workaround. A proper content view request (SOP v2.3) must still
be raised for a permanent solution.

## Risk Assessment

| Scenario | Risk Level |
|----------|-----------|
| Production host missing package blocking deployed service | High |
| QA host missing package blocking test pipeline | Medium |
| Dev host missing package blocking developer workflow | Low |
| Package version mismatch (older version installed) | Low |

## Output

Structure your analysis as a `TicketPayload` using the `create-ticket` skill:

- Set `area` to `"linux"` for all package management issues
- Set `risk` based on lifecycle environment (Prod = high, QA = medium, Dev = low)
- Include the specific SOP action in `recommended_action`
- Reference the Satellite content view and lifecycle environment in `description`
- Include the self-service workaround in `issues` if the host is in the Dev lifecycle
```

- [ ] Commit

```bash
git add skills/analyze-package-management/SKILL.md
git commit -m "feat: add analyze-package-management skill with Meridian Financial Satellite SOPs"
```

---

## Task 2: Create plays repo files

**Repo:** `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays`

**Files:**
- Create: `playbooks/install-python314.yml`
- Create: `configs/subagents-with-sre-package-mgmt.yaml`
- Create: `configs/analyze-package-management-SKILL.md`
- Modify: `configs/subagents-oss-models.yaml`

- [ ] Create `playbooks/install-python314.yml`

```yaml
---
- name: Install Python 3.14
  hosts: all
  become: true
  tasks:
    - name: Install python3.14
      ansible.builtin.dnf:
        name: python3.14
        state: present
```

- [ ] Create `configs/subagents-with-sre-package-mgmt.yaml`

Read `configs/subagents-with-sre-ssh.yaml` for structure reference. The new file replaces `sre_ssh` with `sre_package_management` and narrows `sre_linux`. Full content:

```yaml
sre_ansible:
  description: >
    Ansible/AAP2 specialist. Delegate automation failures: playbook syntax,
    role/collection errors, credential issues, execution environment problems,
    variable resolution, job template misconfiguration.
  model: claude-sonnet-4-6
  system_prompt: |
    You are a senior Ansible and AAP2 SRE. You receive incident data from failed
    AAP2 jobs and perform root-cause analysis on automation-related failures.

    Always:
    - Read the incident context (incident.json) first
    - Identify the exact failing task, role, and module
    - Check for credential, collection, or execution environment issues
    - Reference Ansible/AAP2 docs for module behavior
    - Provide specific, actionable recommendations

    Use the create-ticket skill to structure your analysis as a TicketPayload.
    Set area to "application" for all Ansible-domain issues.
  tools:
    - web_search
  skills:
    - ./skills/analyze-ansible-failure/
    - ./skills/create-ticket/
    - ./skills/common/

sre_linux:
  description: >
    Linux specialist. Delegate host-level failures: systemd services, SELinux,
    filesystem/permissions. Does NOT handle package manager or Satellite issues
    — those go to sre_package_management.
  model: claude-sonnet-4-6
  system_prompt: |
    You are a senior Linux SRE. You receive incident data from failed AAP2 jobs
    and perform root-cause analysis on host-level Linux issues.

    Always:
    - Read the incident context (incident.json) first
    - Look for systemd unit failures, SELinux denials, permission issues
    - Provide specific commands and config changes as recommendations

    Use the create-ticket skill to structure your analysis as a TicketPayload.
    Set area to "linux" for all Linux-domain issues.
  tools:
    - web_search
  skills:
    - ./skills/analyze-linux-failure/
    - ./skills/create-ticket/
    - ./skills/common/

sre_openshift:
  description: >
    OpenShift/Kubernetes specialist. Delegate cluster failures: pod scheduling,
    image pull, RBAC, operator lifecycle, namespace/quota, routes/services.
  model: claude-sonnet-4-6
  system_prompt: |
    You are a senior OpenShift/Kubernetes SRE. You receive incident data from
    failed AAP2 jobs and perform root-cause analysis on cluster-related issues.

    Always:
    - Read the incident context (incident.json) first
    - Check for pod lifecycle issues (CrashLoopBackOff, ImagePullBackOff)
    - Look for RBAC/service account problems, resource limits, quota exhaustion
    - Consider operator and CRD issues
    - Reference upstream Kubernetes docs for version-specific behavior

    Use the create-ticket skill to structure your analysis as a TicketPayload.
    Set area to "kubernetes" for all OpenShift-domain issues.
  tools:
    - web_search
  skills:
    - ./skills/analyze-openshift-failure/
    - ./skills/create-ticket/
    - ./skills/common/

sre_networking:
  description: >
    Networking specialist. Delegate connectivity failures: DNS resolution,
    proxy/TLS issues, routing, firewall rules, unreachable hosts. Does NOT
    handle SSH credential failures — those go to sre_ssh.
  model: claude-sonnet-4-6
  system_prompt: |
    You are a senior network engineer. You receive incident data from failed
    AAP2 jobs and perform root-cause analysis on connectivity issues.

    Always:
    - Read the incident context (incident.json) first
    - Work bottom-up: DNS, routing, firewall, TLS
    - Consider proxy configuration and certificate errors
    - Verify host reachability patterns

    Use the create-ticket skill to structure your analysis as a TicketPayload.
    Set area to "networking" for all networking-domain issues.
  tools:
    - web_search
  skills:
    - ./skills/analyze-networking-failure/
    - ./skills/create-ticket/
    - ./skills/common/

sre_package_management:
  description: >
    Package management specialist. Delegate package installation failures:
    DNF/YUM errors, missing or disabled repositories, RHN/Satellite content
    gaps, module stream conflicts, CRB/EPEL requirements. Does NOT handle
    systemd, filesystem, or SELinux issues — those go to sre_linux.
  model: claude-sonnet-4-6
  system_prompt: |
    You are a senior SRE specialising in Red Hat package management and
    Satellite content delivery. You receive incident data from failed AAP2
    jobs and perform root-cause analysis on package installation failures.

    Always:
    - Read the incident context (incident.json) first
    - Identify the exact package name and the dnf error (no match, disabled
      repo, metadata failure, module conflict)
    - Check whether the package requires CRB, EPEL, or a custom content view
    - Reference the analyze-package-management skill for Meridian Financial's
      Satellite topology and SOP procedures
    - Recommend the specific SOP action (content view request, repo enablement,
      fast-track escalation)

    Use the create-ticket skill to structure your analysis as a TicketPayload.
    Set area to "linux" for all package management issues.
  tools:
    - web_search
  skills:
    - ./skills/analyze-package-management/
    - ./skills/create-ticket/
    - ./skills/common/

reviewer:
  description: >
    Quality reviewer. Validates ticket analysis for coherence, confidence
    justification, and actionable recommendations before submission.
  model: claude-3-5-haiku
  system_prompt: |
    You review incident tickets produced by SRE specialists analyzing AAP2 job
    failures. Your job is quality assurance — not re-analysis.

    Use the review-ticket skill checklist to validate the ticket.

    Return one of:
    - "approved" with optional amendments (corrections to fields)
    - "escalate" with a specific reason why the analysis is inadequate

    Be concise. Do not re-do the analysis — only validate it.
  tools: []
  skills:
    - ./skills/review-ticket/
```

- [ ] Create `configs/analyze-package-management-SKILL.md`

This is identical content to `skills/analyze-package-management/SKILL.md` (Task 1) — copy verbatim. Students download this file and place it on the Athena PVC at `skills/analyze-package-management/SKILL.md`.

- [ ] Update `configs/subagents-oss-models.yaml`

Replace the `sre_ssh` entry with `sre_package_management` (model: `qwen3-235b`). Also narrow `sre_linux` (same narrowing as above but with model `qwen3-235b`). Add `sre_package_management` with model `qwen3-235b`. The file should have the same structure as `subagents-with-sre-package-mgmt.yaml` but with ALL models set to `qwen3-235b` including reviewer.

- [ ] Commit and push

```bash
git add playbooks/install-python314.yml \
        configs/subagents-with-sre-package-mgmt.yaml \
        configs/analyze-package-management-SKILL.md \
        configs/subagents-oss-models.yaml
git commit -m "feat: add sre_package_management agent config and Python 3.14 playbook for Module 3 redesign"
git push
```

---

## Task 3: Add job template to deepagents-aiops role

**Repo:** `/Users/tok/Dropbox/PARAL/Resources/repos/deepagents-aiops`

**Files:**
- Modify: `roles/ocp4_workload_aap2_tenant_config/defaults/main.yml` (or wherever job templates are defined — read the role first)

- [ ] Read existing job template definitions

```bash
grep -r "Install\|job_template\|playbook" \
  roles/ocp4_workload_aap2_tenant_config/defaults/main.yml | head -40
```

Look for the list of job templates (likely `ocp4_workload_aap2_tenant_config_job_templates`). Find the entry for "03 Install Web Server" as the model — copy its structure for the new template.

- [ ] Add "10 Install Python 3.14" job template

Add a new entry to the job templates list following the same pattern as "03 Install Web Server". The new template:
- Name: `"10 Install Python 3.14"`
- Playbook: `install-python314.yml`
- Credential: machine credential (same as "03 Install Web Server")
- Inventory: same RHEL VM inventory as "03 Install Web Server"
- Organization: tenant org (same pattern)

- [ ] Commit and push

```bash
git add roles/ocp4_workload_aap2_tenant_config/
git commit -m "feat: add '10 Install Python 3.14' job template for Module 3 redesign"
git push
```

---

## Task 4: Update showroom Module 3 content

**Repo:** `/Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-showroom`

**Files:**
- Modify: `content/modules/ROOT/pages/05-module-03-first-agent.adoc`

- [ ] Read the existing Module 3 file

```bash
cat content/modules/ROOT/pages/05-module-03-first-agent.adoc
```

Also read the attributes/variables file to find `{gitea_url}` and similar substitutions used in the showroom.

- [ ] Rewrite Module 3 with the new narrative

The new flow replaces the sre_ssh exercise with sre_package_management. Key changes:

**Exercise 1 (was: launch "08 Deploy Monitoring Agent"):**
Now: Launch "10 Install Python 3.14" and observe sre_linux handle it with generic analysis. Student visits Kira to see the ticket — note that it mentions dnf errors but has no Satellite context, no SOP reference, no content view knowledge.

**Exercise 2 (was: explore architecture):**
Keep the ConfigMap / PVC / extensibility exploration — this section is unchanged.

**Exercise 3 (was: build sre_ssh):**
Now: Build sre_package_management:
- Create skill directory on PVC
- Download `analyze-package-management-SKILL.md` from Gitea → place at `skills/analyze-package-management/SKILL.md` on PVC
- Download `subagents-with-sre-package-mgmt.yaml` from Gitea → patch ConfigMap
- `oc rollout restart deployment/athena`

**Exercise 4 (was: test with "02 Ping RHEL Admin"):**
Now: Launch "10 Install Python 3.14" again. Same job. Same error. But now sre_package_management handles it — ticket references Meridian Financial's Satellite topology, recommends SOP v2.3 content view request, mentions CRB/EPEL requirements, provides self-service Dev workaround.

**Exercise 5 (was: compare tickets):**
Now: Compare the two Kira tickets side by side — same failure, different specialist. Key points to highlight: Satellite HA topology, content view per-project model, SOP v2.3 reference, fast-track escalation path.

AsciiDoc conventions to follow:
- `role="execute"` on all source blocks students should run
- `link=self` (not `window=blank`) for any image lightbox links
- No trailing period after credential examples
- No blank line after `====` admonition delimiter
- Use `{user}` and `{password}` not `{guid}` for credentials
- Use `{gitea_url}` for Gitea links

- [ ] Commit and push

```bash
git add content/modules/ROOT/pages/05-module-03-first-agent.adoc
git commit -m "feat: redesign Module 3 — replace sre_ssh with sre_package_management, Python 3.14 failure scenario"
git push
```

---

## Task 5: Rebuild and push Athena image

**Repo:** `/Users/tok/Dropbox/PARAL/Projects/summit-2026-lb2645-agentic-devops/athena-aiops-deep-agent`

This bakes the new skill into the image for future tenant provisioning.

- [ ] Remove stale local manifest and rebuild

```bash
podman rmi quay.io/rhpds/athena-aiops:latest 2>/dev/null || true
make push
```

Expected: multi-arch manifest build (linux/amd64 + linux/arm64) pushed to `quay.io/rhpds/athena-aiops:latest`.

- [ ] Verify skill is in the image

```bash
podman run --rm --entrypoint cat quay.io/rhpds/athena-aiops:latest \
  /app/skills/analyze-package-management/SKILL.md | head -5
```

Expected: first lines of the SKILL.md content.

- [ ] Push Athena git changes

```bash
git push
```

---

## Task 6: Update all 14 tenant Gitea repos

Push the new plays repo files to all tenant Gitea repos via the admin API.

**Gitea admin credentials:** `gitea-admin` / `giteapassword123` (reset earlier in session)
**Gitea URL:** `https://gitea.apps.cluster-d9lfp.dynamic.redhatworkshops.io`

- [ ] Push `configs/subagents-with-sre-package-mgmt.yaml` to all tenants

```bash
GITEA_URL="https://gitea.apps.cluster-d9lfp.dynamic.redhatworkshops.io"
GITEA_PASS="giteapassword123"
FILE_PATH="configs/subagents-with-sre-package-mgmt.yaml"
FILE_CONTENT=$(base64 < /Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/configs/subagents-with-sre-package-mgmt.yaml)

USERS=(user-429bc user-42ht6 user-72l74 user-7p7dj user-blqnr user-bpplm user-jdqzc user-l9wq7 user-mjvrf user-nlsqp user-nxc6b user-vggdq user-wdq4d user-z9q9c)

for USER in "${USERS[@]}"; do
  # File doesn't exist yet — use POST not PUT
  RESULT=$(curl -s -o /dev/null -w "%{http_code}" -u "gitea-admin:$GITEA_PASS" \
    -X POST "$GITEA_URL/api/v1/repos/$USER/agentic-devops-plays/contents/$FILE_PATH" \
    -H "Content-Type: application/json" \
    -d "{\"message\":\"feat: add sre_package_management config for Module 3\",\"content\":\"$FILE_CONTENT\"}")
  echo "$USER: $RESULT"
done
```

- [ ] Push `configs/analyze-package-management-SKILL.md` to all tenants (same pattern, POST)

- [ ] Push updated `configs/subagents-oss-models.yaml` to all tenants (PUT with SHA — file already exists)

```bash
FILE_PATH="configs/subagents-oss-models.yaml"
FILE_CONTENT=$(base64 < /Users/tok/Dropbox/PARAL/Resources/repos/agentic-aiops-plays/configs/subagents-oss-models.yaml)

for USER in "${USERS[@]}"; do
  SHA=$(curl -s -u "gitea-admin:$GITEA_PASS" \
    "$GITEA_URL/api/v1/repos/$USER/agentic-devops-plays/contents/$FILE_PATH" \
    | python3 -c "import json,sys; print(json.load(sys.stdin).get('sha',''))")
  if [ -z "$SHA" ]; then echo "$USER: not found"; continue; fi
  RESULT=$(curl -s -o /dev/null -w "%{http_code}" -u "gitea-admin:$GITEA_PASS" \
    -X PUT "$GITEA_URL/api/v1/repos/$USER/agentic-devops-plays/contents/$FILE_PATH" \
    -H "Content-Type: application/json" \
    -d "{\"message\":\"feat: swap sre_ssh for sre_package_management in OSS models config\",\"content\":\"$FILE_CONTENT\",\"sha\":\"$SHA\"}")
  echo "$USER: $RESULT"
done
```

- [ ] Push `playbooks/install-python314.yml` to all tenants (POST — new file)

---

## Task 7: Add job template to existing tenants via AAP2 API

Existing tenants can't be re-provisioned. Add "10 Install Python 3.14" to their AAP2 orgs via the API.

**AAP2 URL:** `https://aap-aap.apps.cluster-d9lfp.dynamic.redhatworkshops.io`
**Admin token:** retrieve from `oc get secret aap-admin-credentials -n aap -o jsonpath='{.data.token}' | base64 -d`

- [ ] Get admin token

```bash
AAP_TOKEN=$(oc get secret aap-admin-credentials -n aap \
  -o jsonpath='{.data.token}' | base64 -d 2>/dev/null || \
  oc get secret aap-admin-credentials -n aap \
  -o jsonpath='{.data.password}' | base64 -d)
AAP_URL="https://aap-aap.apps.cluster-d9lfp.dynamic.redhatworkshops.io"
echo "Token acquired: ${AAP_TOKEN:0:10}..."
```

- [ ] Find the credential ID, project ID, and inventory ID for each tenant org

```bash
# List all orgs to find tenant orgs
curl -sk -H "Authorization: Bearer $AAP_TOKEN" \
  "$AAP_URL/api/controller/v2/organizations/?page_size=50" \
  | python3 -c "import json,sys; orgs=json.load(sys.stdin); [print(o['id'], o['name']) for o in orgs['results']]"
```

- [ ] For each tenant org, create the "10 Install Python 3.14" job template

Use the existing "03 Install Web Server" template as the reference — find its credential, project, and inventory, then create the new template with:
- name: `"10 Install Python 3.14"`
- playbook: `install-python314.yml`
- Same project, inventory, and machine credential as "03 Install Web Server"

```bash
# Get "03 Install Web Server" template details for reference
curl -sk -H "Authorization: Bearer $AAP_TOKEN" \
  "$AAP_URL/api/controller/v2/job_templates/?name=03+Install+Web+Server&page_size=5" \
  | python3 -c "import json,sys; t=json.load(sys.stdin)['results'][0]; print(json.dumps({k: t[k] for k in ['project','inventory','credentials','organization','become_enabled','ask_variables_on_launch']}, indent=2))"
```

Then POST the new template for each org. Script iterates tenant orgs, finds their "03 Install Web Server" project/inventory, and creates "10 Install Python 3.14".

---

## Verification

- [ ] Verify skill exists in running Athena pod

```bash
oc exec -n user-mjvrf-agentic deploy/athena -- \
  ls /skills/analyze-package-management/ 2>/dev/null && echo "PVC has skill" || echo "PVC skill absent (expected for existing tenants — student downloads it)"
```

- [ ] Verify new configs in user-mjvrf Gitea

```bash
curl -sL "https://gitea.apps.cluster-d9lfp.dynamic.redhatworkshops.io/user-mjvrf/agentic-devops-plays/raw/branch/main/configs/subagents-with-sre-package-mgmt.yaml" \
  | grep "sre_package_management"
```

Expected: `sre_package_management:` appears in output.

- [ ] Verify new job template exists in AAP2 for user-mjvrf

Check the AAP2 UI or API for "10 Install Python 3.14" in the user-mjvrf org.
