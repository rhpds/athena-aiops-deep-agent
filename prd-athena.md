# PRD: Athena — Agentic AIOps Ticketing Assistant for AAP2 on OpenShift

## Summary

Build **Athena**, an agentic AIOps service that listens for failed Ansible Automation Platform 2 (AAP2) Controller jobs, gathers the related failure artifacts, analyzes the error using a Deep Agents-based orchestration layer, and creates a structured incident or trouble ticket in an external ticketing system called `kira` via API.

Athena should be designed as a practical first Deep Agents lab for OpenShift: small enough to ship quickly, but structured to demonstrate real agentic patterns including skills-first execution, dynamic subagent loading from YAML, filesystem-backed context, and external system integration.

## Product Goals

- Automatically ingest AAP2 job failure events.
- Retrieve enough execution context to analyze likely root cause.
- Route analysis to the most appropriate specialist SRE subagent.
- Produce a structured ticket with:
  - probable root cause
  - confidence score
  - validation steps
  - recommended fixes
  - code/configuration change suggestions
- Send the ticket to `kira` through an API adapter.
- Optionally notify Rocket.Chat with a summary and a link to the created ticket.
- Demonstrate a clean Deep Agents architecture on OpenShift.

## Non-Goals

- Athena does not execute remediation automatically in v1.
- Athena does not modify AAP2 jobs, playbooks, inventories, or clusters in v1.
- Athena does not attempt multi-ticket correlation or historical incident clustering in v1.
- Athena does not require a UI in v1; API + logs are sufficient.

## Primary User

Platform engineers, SREs, and automation teams operating AAP2 and OpenShift who want failed automation runs triaged faster and more consistently.

## Key User Story

As an SRE or automation engineer, when an AAP2 job fails, I want Athena to analyze the failure and open a high-quality ticket automatically so that I can review the likely cause and next actions without manually inspecting raw logs first.

## Functional Overview

### High-Level Flow

1. Athena starts inside OpenShift.
2. Athena authenticates to AAP2 Controller using environment-provided credentials.
3. Athena ensures a webhook registration exists for relevant job failure events.
4. AAP2 sends a webhook to Athena when a job fails.
5. Athena retrieves:
   - the error log / stdout / event output
   - job metadata
   - job template details
   - project / playbook / inventory / execution environment references where available
6. Athena passes the normalized incident package to the Deep Agent `ops_manager`.
7. `ops_manager` classifies the failure domain using skills-first behavior.
8. `ops_manager` delegates to one specialist SRE subagent.
9. The selected SRE subagent performs root-cause analysis using:
   - relevant skills
   - optional tools such as web search or documentation lookup
   - attached job context and code snippets
10. Athena produces a canonical `TICKET.md`.
11. A `reviewer` step validates ticket quality and required fields.
12. An `informer` or `logger` component sends the ticket to:
   - `kira` via API
   - optionally Rocket.Chat with a summary and ticket URL
13. Athena stores structured logs and trace metadata for observability.

## Deep Agents Architecture

### Design Principles

- **Skills first**: prefer skills over large tool sets wherever possible, because skills reduce context load and let the agent progressively load detailed instructions only when needed. [web:10][page:2]
- **Subagents on demand**: create specialist subagents only when classification requires them.
- **Filesystem-backed context**: use Deep Agents with a filesystem backend so the agent can read `AGENTS.md`, skill folders, and generated files like `TICKET.md`, matching the documented pattern in LangChain’s example. [page:1]
- **YAML-defined subagents**: store subagent definitions in `subagents.yaml`, loaded at startup by application code, since Deep Agents examples externalize subagent config this way rather than auto-loading it natively from files. [page:1]
- **Single service deployment**: package as one Python service in one container for the initial lab.
- **Stateless pod, externalized config**: use ConfigMaps, Secrets, and PVCs so agent behavior can evolve without rebuilding the container.

### Main Agent

#### `ops_manager`

Responsibilities:
- Accept normalized incident input.
- Determine whether available evidence is sufficient.
- Invoke classification skill.
- Select the correct specialist subagent.
- Ensure final output conforms to the ticket schema.
- Escalate to fallback/manual-review path if confidence is too low.

### Specialist Subagents

Subagents are ephemeral and instantiated on demand by `ops_manager`.

#### `sre_ansible`
Handles:
- playbook syntax and logic issues
- role and collection problems
- inventory problems
- credential or authentication issues
- execution environment issues
- missing modules / collections
- variable resolution issues
- controller / job template parameter misuse

#### `sre_linux`
Handles:
- package manager errors like `dnf`
- user/group management failures
- file permission issues
- systemd/service failures
- SELinux issues
- filesystem space or mount issues
- host OS configuration problems
- Satellite-related package/content problems

#### `sre_openshift`
Handles:
- pod scheduling/startup failures
- image pull and registry issues
- route/service/networking issues
- operator lifecycle issues
- RBAC/service account problems
- Kubernetes API resource failures
- namespace/quota/limit issues
- cluster policy or admission failures

### Supporting Roles

#### `reviewer`
Checks:
- ticket completeness
- schema compliance
- actionability of recommendations
- duplication or contradiction
- whether the confidence level supports automatic submission

#### `informer`

Responsible for delivering outputs to sink systems using channel-specific formatting and adapter logic channel adapters.

## Skills and Tooling Model

### Skills

Athena should support a `skills/` directory mounted from a PVC. Skills are folders containing `SKILL.md` plus optional templates or helper files, which matches the Anthropic-style skill pattern Deep Agents now supports. [page:2]

Proposed initial skills:

- `error-classifier`
  - classify failure domain
  - emit domain, confidence, rationale
- `analyze-ansible-failure`
- `analyze-linux-failure`
- `analyze-openshift-failure`
- `create-ticket`
  - produce canonical `TICKET.md`
- `output-to-kira`
  - map canonical ticket into Kira payload format
- `output-to-rocket-chat`
  - create a concise notification body with ticket link
- `review-ticket`
  - ensure required sections exist and are coherent

### Tools

Keep the tool surface small. Deep Agents guidance emphasizes that generalist agents can stay effective with a relatively small toolset when filesystem and shell/context patterns do most of the heavy lifting. [web:1][page:2]

Proposed tools:
- `aap2_get_job`
- `aap2_get_job_events`
- `aap2_get_job_stdout`
- `aap2_get_job_template`
- `aap2_get_related_artifacts`
- `kira_create_ticket`
- `rocketchat_post_message`
- `web_search` via Tavily, optional
- `docs_search` or MCP-backed documentation lookup, optional
- `read_file`, `write_file` through Deep Agents backend
- standard tracing/logging hooks

## Configuration Model

### Runtime Files

#### `AGENTS.md`
Global operating instructions for Athena:
- purpose
- response style
- triage rules
- escalation policy
- output standards
- required ticket sections
- confidence thresholds
- date/time variable guidance

Deep Agents examples load `AGENTS.md` through the `memory` parameter so the contents become persistent instructions for the agent. [page:1]

#### `subagents.yaml`
Mounted from ConfigMap and hot-reloadable on pod restart.

Contains:
- subagent name
- description
- model
- system prompt
- allowed tools
- preferred skills
- delegation rules

The LangChain content-builder example explicitly shows a helper function that reads YAML and maps named tools into runtime subagent definitions. [page:1]

#### `skills/`
Mounted from PVC so skills can be added without rebuilding the image.

#### Templates
Examples:
- `templates/TICKET.md.j2` or `template-ticket.md`
- `templates/output-kira.md`
- `templates/output-rocketchat.md`

## Canonical Data Contracts

### Incoming Webhook Payload
Athena must normalize incoming AAP2 webhook payloads into an internal incident envelope.

Suggested internal structure:

```json
{
  "event_id": "string",
  "received_at": "ISO-8601 timestamp",
  "source": "aap2",
  "job": {
    "id": "string",
    "name": "string",
    "status": "failed",
    "template_id": "string",
    "template_name": "string",
    "project": "string",
    "inventory": "string",
    "execution_environment": "string",
    "started_at": "ISO-8601 timestamp",
    "finished_at": "ISO-8601 timestamp"
  },
  "artifacts": {
    "stdout": "string",
    "error_excerpt": "string",
    "events": [],
    "playbook_path": "string|null",
    "related_files": []
  },
  "context": {
    "cluster": "string|null",
    "environment": "dev|test|stage|prod|null",
    "namespace": "string|null"
  }
}

