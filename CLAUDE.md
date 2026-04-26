# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Project Overview

**Athena** is an agentic AIOps service that listens for failed AAP2 (Ansible Automation Platform 2) Controller jobs, analyzes failures using a Deep Agents orchestration layer, and creates structured incident tickets in the `kira` ticketing system via API. Notifications are posted to Rocket.Chat `#support`. Designed as a practical Deep Agents lab for OpenShift.

This repo evolves from `../1st-pass-deepagents-poc/` which proved out the Deep Agents pattern with a simpler ops_manager + SRE subagent setup. Athena adds AAP2 webhook ingestion, ticket generation, the Kira adapter, a reviewer step, and OpenShift deployment.

## Commands

```bash
# Install dependencies
uv sync

# Install with dev tools
uv sync --extra dev

# Run the service (requires env vars — see athena/config.py)
uv run python -m athena

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_adapters/test_kira.py::test_create_ticket_sends_correct_payload -v

# Lint and format
uv run ruff check .
uv run ruff format --check .

# Auto-fix lint and format
uv run ruff check --fix . && uv run ruff format .
```

## Architecture

### Hybrid with Smart Reviewer

Agents handle classification, root-cause analysis, and intelligent review. Deterministic Python code handles API plumbing — Kira submission, Rocket.Chat notification, schema validation. The agent boundary falls where LLM reasoning adds value.

### Deep Agents Pattern

- `AGENTS.md` — loaded as persistent memory (system prompt) for `ops_manager` via `MemoryMiddleware`
- `skills/` — per-subagent skill directories loaded via `SkillsMiddleware`; each skill is a folder containing `SKILL.md`
- `subagents.yaml` — defines specialist subagents; loaded by `load_subagents()` in `athena/agents/pipeline.py`
- `templates/ticket.md.j2` — Jinja2 ticket template

Built-in deepagents tools: `write_file`, `read_file`, `edit_file`, `ls`, `glob`, `grep`, `execute`, `task` (subagent delegation), `write_todos`.

### Agent Hierarchy

```
AAP2 webhook → athena service → ops_manager (main agent)
                                    ├── sre_ansible     (playbook/role/collection/credential)
                                    ├── sre_linux       (dnf/systemd/SELinux/filesystem/Satellite)
                                    ├── sre_openshift   (pod/image/RBAC/operator/networking)
                                    └── sre_networking  (DNS/proxy/TLS/routing/firewall)

ops_manager → reviewer (validates ticket quality on Haiku)
           → returns TicketPayload (structured output)

submission.py → Kira API (create ticket + issues)
             → Rocket.Chat #support (notification)
```

### Flow

1. AAP2 sends a webhook to `POST /api/v1/webhook/aap2` (or user triggers `POST /api/v1/analyze`)
2. `services/ingestion.py` retrieves job artifacts via `adapters/aap2.py` and builds `IncidentEnvelope`
3. `agents/pipeline.py` writes `incident.json`, invokes `ops_manager`
4. `ops_manager` classifies domain using `error-classifier` skill
5. Delegates to one specialist SRE subagent via `task` tool
6. SRE subagent performs root-cause analysis using domain skills
7. `reviewer` subagent validates ticket quality
8. `ops_manager` returns structured `TicketPayload` JSON
9. `services/submission.py` sends to Kira, posts to Rocket.Chat

### Code Layout

```
athena/
├── config.py        # Pydantic BaseSettings — all env vars
├── models.py        # IncidentEnvelope, TicketPayload, DOMAIN_TO_KIRA_AREA
├── app.py           # FastAPI app, lifespan (client init, webhook registration)
├── adapters/        # Async HTTP clients: aap2.py, kira.py, rocketchat.py
├── services/        # ingestion.py (AAP2 → IncidentEnvelope), submission.py (→ Kira + Rocket.Chat)
├── agents/          # pipeline.py (Deep Agents wiring), tools.py (@tool functions)
└── routes/          # health.py (/healthz, /readyz), webhook.py, analyze.py
```

### Skills

Skills live in `skills/` (mountable PVC). Each is a folder with `SKILL.md`:

- `error-classifier` — classify failure domain, emit domain/confidence/rationale
- `analyze-ansible-failure`, `analyze-linux-failure`, `analyze-openshift-failure`, `analyze-networking-failure`
- `create-ticket` — guide structured TicketPayload output
- `review-ticket` — validate coherence, confidence, actionability
- `common/log-analysis` — shared Ansible stdout parsing

## Adding a New Subagent

1. Add entry to `subagents.yaml` with description, model, system_prompt, tools, skills
2. Add any new `@tool` functions in `athena/agents/tools.py`
3. Register tool names in `available_tools` dict inside `load_subagents()` in `athena/agents/pipeline.py`
4. Create skill directory `skills/<domain>/` with `SKILL.md`
5. Update `AGENTS.md` domain awareness section

## Adding a New Skill

1. Create `skills/<domain>/<skill-name>/SKILL.md`
2. Skills are auto-discovered by `SkillsMiddleware` — no code registration needed
3. Add the source path to the subagent's `skills:` array in `subagents.yaml`
4. Shared skills go in `skills/common/`

## Deployment

Single Python service in one container on OpenShift via Helm chart (`deploy/helm/athena/`):
- `AGENTS.md` and `subagents.yaml` baked into image, overridable via ConfigMap
- Credentials (AAP2, Kira, Rocket.Chat, MaaS) from Secrets
- `skills/` from PVC (add skills without rebuilding the image)
- OpenShift Route exposes webhook endpoint for AAP2
- Auto-registers AAP2 webhook notification template on startup (idempotent)

## Key Conventions

- Python 3.13 — always use `uv`, never `pip`
- Always use Pydantic V2 for structured outputs with OpenAI API
- Skills first: prefer skills over large tool sets to reduce context load
- Models route through MaaS gateway (OpenAI-compatible) — prefixed `openai/` in subagents.yaml
- Subagent models default to `openai/claude-sonnet-4-6`, reviewer uses `openai/claude-3-5-haiku`
- Keep the tool surface small — filesystem and skills do the heavy lifting
- `prd-athena.md` is the authoritative product requirements document
- Design spec at `docs/superpowers/specs/2026-04-15-athena-aiops-design.md`

## Resources and References

- [LangChain Deep Agents repo](https://github.com/langchain-ai/deepagents.git) — framework source and `examples/` directory for implementation patterns
- [Kira ticketing system](https://github.com/tonykay/kira) — source and deployment
- [Kira OpenAPI spec](https://github.com/tonykay/kira/blob/main/docs/api/openapi.yaml) — authoritative field/enum reference
- [Introducing Deep Agents](https://blog.langchain.com/deep-agents/)
- [Doubling Down on Deep Agents](https://blog.langchain.com/doubling-down-on-deepagents/)
- [Using Skills with Deep Agents](https://blog.langchain.com/using-skills-with-deep-agents/)
- [Building Multi-Agent Applications with Deep Agents](https://blog.langchain.com/building-multi-agent-applications-with-deep-agents/)


<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:ca08a54f -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

## Session Completion

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd dolt push
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
<!-- END BEADS INTEGRATION -->
