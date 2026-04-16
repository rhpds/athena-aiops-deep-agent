# Athena AIOps

An agentic AIOps service that automatically analyzes failed Ansible Automation Platform 2 (AAP2) jobs, diagnoses root causes, and creates structured incident tickets — built on [LangChain Deep Agents](https://github.com/langchain-ai/deepagents), a 2nd-generation agentic framework deployed to OpenShift, Kubernetes, or locally via Podman or Docker.

## Why Athena

When an AAP2 automation job fails, someone has to read the logs, figure out what went wrong, decide who should fix it, and open a ticket. That process is slow, inconsistent, and pulls SREs away from higher-value work.

Athena does this automatically. When a job fails, Athena retrieves the execution output, classifies the failure domain, delegates to a specialist AI agent for root-cause analysis, and creates a detailed ticket in [Kira](https://github.com/tonykay/kira) with evidence, confidence scores, and specific remediation steps. A notification lands in Rocket.Chat within minutes.

This isn't a simple "summarize the logs" tool. Athena uses a multi-agent architecture where an operations manager agent triages incidents and delegates to specialist SRE agents — each with domain-specific skills and knowledge — mirroring how a real ops team works. The result is tickets that look like they were written by an experienced SRE, not a chatbot.

## How It Works

```
  AAP2 Controller                    Athena Service                         External Systems
 ┌──────────────┐     webhook     ┌─────────────────────┐               ┌──────────────────┐
 │  Job fails   │────────────────>│  Ingest & normalize │               │                  │
 │              │                 │         │            │               │   Kira Ticketing  │
 └──────────────┘                 │         v            │   ticket      │                  │
                                  │  ┌─────────────┐    │──────────────>│  - root cause     │
                                  │  │ ops_manager  │    │               │  - confidence     │
                                  │  │  (classify)  │    │               │  - remediation    │
                                  │  └──────┬───────┘    │               └──────────────────┘
                                  │         │ delegate   │
                                  │    ┌────┼────┐       │               ┌──────────────────┐
                                  │    v    v    v       │   notify      │                  │
                                  │  ┌───┐┌───┐┌───┐    │──────────────>│  Rocket.Chat     │
                                  │  │SRE││SRE││SRE│    │               │  #support         │
                                  │  └─┬─┘└───┘└───┘    │               └──────────────────┘
                                  │    │                 │
                                  │    v                 │               ┌──────────────────┐
                                  │  ┌──────────┐       │               │                  │
                                  │  │ reviewer  │       │               │  MaaS LLM Gateway│
                                  │  │ (validate)│       │<─────────────>│  (Claude, GPT,   │
                                  │  └──────────┘       │   LLM calls   │   Gemini, etc.)  │
                                  └─────────────────────┘               └──────────────────┘
```

**Step by step:**

1. **AAP2 webhook fires** — Athena auto-registers a notification template on startup; when any job fails, AAP2 POSTs to Athena
2. **Ingest** — Athena fetches job stdout, events, metadata, and template details from the AAP2 API
3. **Classify** — The `ops_manager` agent uses the `error-classifier` skill to determine the failure domain (Ansible, Linux, OpenShift, or networking)
4. **Delegate** — `ops_manager` routes to the right specialist via the Deep Agents `task` tool
5. **Analyze** — The specialist SRE agent performs root-cause analysis using domain-specific skills, producing a structured ticket with evidence, confidence, and remediation
6. **Review** — A `reviewer` agent validates the ticket for coherence, justified confidence, and actionable recommendations
7. **Submit** — Deterministic code sends the ticket to Kira and posts a notification to Rocket.Chat

## Architecture: Deep Agents Patterns

Athena is built on [Deep Agents](https://github.com/langchain-ai/deepagents), a 2nd-generation agentic framework that moves beyond simple "LLM + tools" to a richer model of agent behavior.

### What makes Deep Agents different

| 1st Gen (ReAct, tool-calling) | 2nd Gen (Deep Agents) |
|-------------------------------|----------------------|
| System prompt is static | **Memory**: `AGENTS.md` loaded as persistent, editable instructions |
| All instructions upfront | **Skills**: Progressive instruction loading — agents discover and load `SKILL.md` files on demand, keeping context focused |
| Single agent or hard-coded chains | **Subagents**: Dynamic delegation via `task` tool — specialists instantiated on demand from `subagents.yaml` |
| State in memory only | **Filesystem backend**: Agents read/write files — incident data, tickets, investigation artifacts |
| Tool-heavy | **Skills-first**: Prefer workflow instructions over large tool sets, reducing context load and improving reasoning |

### How Athena uses these patterns

```
AGENTS.md                    ← ops_manager persona, triage protocol, escalation rules
subagents.yaml               ← 4 SRE specialists + reviewer, declaratively configured
skills/
├── error-classifier/        ← classify failure domain
├── analyze-ansible-failure/  ← Ansible-specific RCA workflow
├── analyze-linux-failure/    ← Linux-specific RCA workflow
├── analyze-openshift-failure/← OpenShift-specific RCA workflow
├── analyze-networking-failure/← Network-specific RCA workflow
├── create-ticket/           ← structured output guidance
├── review-ticket/           ← quality validation checklist
└── common/log-analysis/     ← shared AAP2 stdout parsing
```

**Agent roster:**

| Agent | Model | Role |
|-------|-------|------|
| `ops_manager` | claude-sonnet-4-6 | Triage, classify, delegate, synthesize |
| `sre_ansible` | claude-sonnet-4-6 | Playbook/role/collection/credential issues |
| `sre_linux` | claude-sonnet-4-6 | dnf/systemd/SELinux/filesystem/Satellite |
| `sre_openshift` | claude-sonnet-4-6 | Pod/image/RBAC/operator/namespace |
| `sre_networking` | claude-sonnet-4-6 | DNS/SSH/proxy/TLS/routing |
| `reviewer` | claude-3-5-haiku | Validate coherence, confidence, actionability |

**Hybrid design:** Agents handle what LLMs are good at — classification, root-cause analysis, quality review. Deterministic Python code handles API plumbing — Kira submission, Rocket.Chat notification, field mapping. The boundary falls exactly where LLM reasoning adds value.

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) package manager
- Access to AAP2 Controller, Kira, Rocket.Chat, and a MaaS-compatible LLM gateway

### Local development

```bash
# Install dependencies
uv sync --extra dev

# Set required environment variables (see athena/config.py for full list)
export AAP2_URL=https://your-aap2-controller
export AAP2_USERNAME=your-user
export AAP2_PASSWORD=your-password
export AAP2_ORGANIZATION=your-org
export KIRA_URL=http://your-kira-api:8000
export KIRA_API_KEY=your-key
export ROCKETCHAT_URL=http://your-rocketchat
export ROCKETCHAT_API_AUTH_TOKEN=your-token
export ROCKETCHAT_API_USER_ID=your-user-id
export LITELLM_API_BASE_URL=https://your-llm-gateway/v1
export LITELLM_VIRTUAL_KEY=your-llm-key

# Run the service
uv run python -m athena

# Run tests
uv run pytest -v

# Lint
uv run ruff check . && uv run ruff format --check .
```

### Manual trigger

```bash
# Analyze a specific failed job
curl -X POST http://localhost:8080/api/v1/analyze \
  -H 'Content-Type: application/json' \
  -d '{"job_id": 42}'
```

### API docs

FastAPI auto-generates OpenAPI documentation at `/docs`.

## Deployment on OpenShift

Athena deploys as a single container via Helm chart.

### Build and push

```bash
# Multi-arch build (amd64 + arm64)
make push

# Or with custom registry
make push IMAGE_REGISTRY=quay.io IMAGE_NAMESPACE=your-org
```

### Deploy

```bash
helm upgrade --install athena deploy/helm/athena/ \
  --set aap2.url=$AAP2_URL \
  --set aap2.username=$AAP2_USERNAME \
  --set aap2.password=$AAP2_PASSWORD \
  --set aap2.organization=$AAP2_ORGANIZATION \
  --set kira.url=$KIRA_URL \
  --set kira.apiKey=$KIRA_API_KEY \
  --set kira.frontendUrl=$KIRA_FRONTEND_URL \
  --set rocketchat.url=$ROCKETCHAT_URL \
  --set rocketchat.apiAuthToken=$ROCKETCHAT_API_AUTH_TOKEN \
  --set rocketchat.apiUserId=$ROCKETCHAT_API_USER_ID \
  --set maas.apiBaseUrl=$LITELLM_API_BASE_URL \
  --set maas.virtualKey=$LITELLM_VIRTUAL_KEY
```

The Helm chart creates:
- **Deployment** with health/readiness probes
- **Service** (ClusterIP on 8080)
- **Route** (TLS edge termination, 5-minute timeout for agent pipeline)
- **Secret** for all credentials
- **PVC** for skills (add skills without rebuilding the image)

On startup, Athena automatically registers its webhook in AAP2 and attaches it to all job templates in the configured organization.

## Extending Athena

### Add a new SRE specialist

1. Add an entry to `subagents.yaml` with description, model, system prompt, tools, and skills
2. Create `skills/analyze-<domain>-failure/SKILL.md` with the diagnostic workflow
3. Update the `error-classifier` skill to recognize the new domain
4. Update `AGENTS.md` domain awareness section

### Add a new skill

1. Create `skills/<domain>/<skill-name>/SKILL.md`
2. Skills are auto-discovered by Deep Agents `SkillsMiddleware` — no code changes needed
3. Reference the skill directory in the subagent's `skills:` array in `subagents.yaml`

### Swap LLM models

Models are configured in `subagents.yaml` and `athena/agents/pipeline.py`. Any model available through your MaaS gateway works — Claude, GPT, Gemini, Llama, Qwen, or any OpenAI-compatible endpoint.

## Deep Agents: A 2nd Generation Agentic Platform

First-generation agent frameworks gave LLMs access to tools and a ReAct loop. That was a breakthrough, but it hit limits: bloated system prompts, no progressive context management, rigid single-agent architectures, and tool sets that grow unwieldy as capabilities expand.

[Deep Agents](https://github.com/langchain-ai/deepagents) represents the next evolution. Instead of stuffing everything into a system prompt, agents load instructions progressively through skills — focused `SKILL.md` files that are discovered and loaded on demand. Instead of one monolithic agent, work is delegated to specialist subagents defined declaratively in YAML. Instead of ephemeral state, agents operate on a filesystem backend where they can read context, write artifacts, and build on each other's work.

The result is agents that behave more like teams than tools. Athena's `ops_manager` doesn't try to be an expert in Ansible, Linux, OpenShift, and networking simultaneously. It triages, delegates, and synthesizes — exactly like a human operations manager. Each specialist focuses on what it knows, using skills that guide its reasoning without overwhelming its context window.

This architecture scales naturally. Adding a new domain (database issues, security incidents, cloud provider failures) means adding a subagent definition and a skill file — not rewriting the orchestration logic or inflating the system prompt.

## Resources

- **Deep Agents Framework**
  - [GitHub Repository](https://github.com/langchain-ai/deepagents.git) — source code and examples
  - [Introducing Deep Agents](https://blog.langchain.com/deep-agents/)
  - [Doubling Down on Deep Agents](https://blog.langchain.com/doubling-down-on-deepagents/)
  - [Using Skills with Deep Agents](https://blog.langchain.com/using-skills-with-deep-agents/)
  - [Building Multi-Agent Applications with Deep Agents](https://blog.langchain.com/building-multi-agent-applications-with-deep-agents/)

- **Athena Dependencies**
  - [Kira Ticketing System](https://github.com/tonykay/kira) — API-first ticket management for AIOps
  - [Kira OpenAPI Spec](https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml) — field and enum reference
