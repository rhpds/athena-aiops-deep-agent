# Module 3 Redesign: sre_package_management Agent

**Date:** 2026-04-26
**Status:** Approved
**Scope:** Replace the Module 3 sre_ssh exercise with a new sre_package_management agent and Python 3.14 failure scenario.

---

## Background

Module 3 previously had students build an `sre_ssh` agent to handle SSH credential failures from job "02 Ping RHEL Admin" (deprecated backdoor key). The routing worked, but the failure was Ansible-level (ansible.builtin.ping + SSH auth error) which `sre_ansible` naturally claims before `sre_ssh` gets a look-in. The pedagogical goal — student builds a new specialist and sees ops_manager route to it — was undermined.

The new design uses a DNF package failure (Python 3.14 not in enabled repos) which is unambiguously in the package management domain, routes cleanly, and gives the new skill rich institutional knowledge to encode about Meridian Financial's Satellite infrastructure and SOPs.

---

## Failure Scenario

**Job template:** "10 Install Python 3.14"
**Playbook:** `install-python314.yml`

```yaml
- name: Install Python 3.14
  hosts: all
  tasks:
    - name: Install python3.14
      ansible.builtin.dnf:
        name: python3.14
        state: present
```

Fails immediately with `No match for argument: python3.14`. Unambiguous, instant, no flakiness. Python 3.14 is not in RHEL 9 base or AppStream repos — requires CRB + EPEL or an internal Satellite content view.

**Narrative:** Meridian Financial's AI/ML pipeline team requires Python 3.14 on the RHEL VM fleet. The package install fails because no content view for the AI/ML project has been requested from the platform team, and CRB is not enabled in the current activation key.

---

## Module 3 Flow (Approach A: show the gap, then fill it)

1. **Launch job** "10 Install Python 3.14" → `sre_linux` handles it (generic "package not found in enabled repos" analysis, no institutional knowledge about Meridian's Satellite topology or SOPs)
2. **Explore the gap** — student reads the ticket in Kira, notes that sre_linux recommends generic `dnf` troubleshooting with no Satellite or SOP context
3. **Add specialist** — student creates `sre_package_management` agent:
   - Downloads `analyze-package-management-SKILL.md` from Gitea → copies to PVC at `skills/analyze-package-management/SKILL.md`
   - Downloads `subagents-with-sre-package-mgmt.yaml` from Gitea → patches ConfigMap
   - `oc rollout restart deployment/athena`
4. **Launch same job again** → `sre_package_management` routes correctly, ticket includes Satellite topology, correct SOP references, and a specific content view request template
5. **Compare tickets** — student sees the qualitative difference between generic and specialist analysis

**Key takeaway:** Same failure. Same ops_manager. Completely different quality of analysis — because you added a specialist with institutional knowledge, not just another generalist.

---

## New Agent: sre_package_management

```yaml
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
```

### sre_linux description narrowing (pre-built config only)

In `subagents-with-sre-package-mgmt.yaml`, `sre_linux` description is narrowed:

**Before:** "Linux specialist. Delegate host-level failures: package manager (dnf/yum), systemd services, SELinux, filesystem/permissions, Satellite content issues."

**After:** "Linux specialist. Delegate host-level failures: systemd services, SELinux, filesystem/permissions. Does NOT handle package manager or Satellite issues — those go to sre_package_management."

Both the `description` and the `system_prompt` of sre_linux are narrowed in the pre-built config — the system_prompt bullet "Consider Satellite content view configuration for package availability" is removed.

Base `subagents.yaml` is **not changed** — sre_linux retains package manager coverage for Module 2 students.

---

## New Skill: analyze-package-management

**Path:** `skills/analyze-package-management/SKILL.md`

### Diagnostic Workflow

1. Read `incident.json` — identify exact package name and DNF error string
2. Classify error type:
   - `No match for argument` → package absent from all enabled repos/content views
   - `Repository X is disabled` → repo exists in Satellite but not in host's activation key
   - `Failed to download metadata` → Satellite reachability or content sync issue
   - `Module or Group X is not available` → AppStream module stream not enabled
3. Determine if package requires CRB, EPEL, or internal content view
4. Select SOP path (see below)

### Meridian Financial Satellite Infrastructure (tribal knowledge)

- **Primary Satellite:** `satellite-primary.meridian.internal` (London DC)
- **Replica Satellite:** `satellite-replica.meridian.internal` (Dublin DC)
- Both are active — "Satellite is unavailable" is almost never the root cause; suspect content view or activation key configuration instead
- Lifecycle environments: **Dev → QA → Prod** — content must be explicitly promoted at each stage
- Content views are **per-team/per-project** — a package in the Platform team's content view is invisible to hosts in the AI/ML project's content view
- CRB (CodeReady Builder) is enabled in Platform and Security content views but **not** in the default base content view used by most RHEL VMs
- EPEL is available in the internal Satellite mirror but must be explicitly included in a content view

### Common Failure Patterns

| Error | Root Cause | SOP Action |
|-------|-----------|------------|
| `No match for argument: python3.14` | Package not in any enabled content view | Request dedicated content view (SOP v2.3) |
| `Repository 'epel' is disabled` | EPEL not in activation key | Request content view update to include EPEL repo |
| `No match for argument: <package>` + CRB needed | CRB not in content view | Include CRB flag in content view request |
| Package in Dev but not Prod | Content view not promoted | Request promotion via fast-track |

### Standard Operating Procedures

**SOP v2.3 — Content View Request**
- Raise a ticket to the Platform team queue: *"New Content View Request — [project name]"*
- Required fields: project name, lifecycle environment, package list, CRB/EPEL requirements, business justification
- Standard SLA: 2 business days
- For Python 3.14 specifically: flag CRB requirement explicitly — Platform team will include `rhel-9-for-x86_64-crb-rpms` and the internal EPEL mirror

**Fast-track escalation** (for production-blocking issues)
- Post in `#platform-satellite` Slack channel with manager approval tag
- Reference the ticket number from the standard request
- SLA: 4 hours during business hours

**Self-service options** (for Dev lifecycle only)
- Enable CRB on individual Dev hosts: `subscription-manager repos --enable codeready-builder-for-rhel-9-x86_64-rpms`
- Not permitted in QA or Prod without Platform team involvement

### Risk Assessment
- **High:** Production host missing a required package for a deployed service
- **Medium:** Dev/QA host missing package — blocks pipeline but not customer-facing
- **Low:** Package version mismatch (newer version available, older installed)

---

## Files Changed

| Repo | File | Change |
|------|------|--------|
| `agentic-aiops-plays` | `playbooks/install-python314.yml` | New |
| `agentic-aiops-plays` | `configs/subagents-with-sre-package-mgmt.yaml` | New (Module 3 pre-built config) |
| `agentic-aiops-plays` | `configs/analyze-package-management-SKILL.md` | New (student downloads to PVC) |
| `agentic-aiops-plays` | `configs/subagents-oss-models.yaml` | Update: swap sre_ssh → sre_package_management (with narrowed sre_linux, all models qwen3-235b) |
| `deepagents-aiops` | `roles/ocp4_workload_aap2_tenant_config/` | New job template "10 Install Python 3.14" |
| `athena-aiops-deep-agent` | `skills/analyze-package-management/SKILL.md` | New (baked into image for new tenants) |
| `agentic-aiops-showroom` | `05-module-03-first-agent.adoc` | Update narrative: replace sre_ssh with sre_package_management |

**Gitea update required:** Push updated configs to all 14 tenant Gitea repos via admin API (same script used previously).

**Existing tenants:** New job template must be added via AAP2 API — cannot re-provision.

**Image rebuild:** Required to bake `analyze-package-management` skill into image for future tenants. Existing tenants download the skill from Gitea as part of the Module 3 exercise (identical pattern to current sre_ssh flow).

---

## What Stays the Same

- Base `subagents.yaml` — untouched
- All existing job templates (01–09) — untouched
- `subagents-with-sre-ssh.yaml` — stays in Gitea, just not used in lab flow
- Module 2 flow — unaffected (sre_linux still handles package failures for Module 2 students)
- Seed job "02 Ping RHEL Admin" — still fires for Module 2 backdrop
- Module 4 narrative — model swap story unchanged; only the agent list updates

---

## Risk

**Low overall.** All changes are additive except:
- sre_linux description narrowing — only in pre-built config, base unchanged
- Module 3 showroom content — doc change only

No changes to provisioning flow, agnosticv catalog, or cluster infrastructure.
