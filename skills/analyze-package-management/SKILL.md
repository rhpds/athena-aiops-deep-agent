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
