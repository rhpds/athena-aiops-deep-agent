# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

@AGENTS.md

## Project Overview

**Athena** is an agentic AIOps service that listens for failed AAP2 (Ansible Automation Platform 2) Controller jobs, analyzes failures using a Deep Agents orchestration layer, and creates structured incident tickets in the `kira` ticketing system via API. Optional Rocket.Chat notifications. Designed as a practical Deep Agents lab for OpenShift.

This repo evolves from `../1st-pass-deepagents-poc/` which proved out the Deep Agents pattern with a simpler ops_manager + SRE subagent setup. Athena adds AAP2 webhook ingestion, ticket generation, the `kira` adapter, and a reviewer step.

## Commands

```bash
# Install dependencies
uv sync

# Run the service
uv run python -m athena

# Run tests
uv run pytest

# Run a single test
uv run pytest tests/test_foo.py::test_name -v

# Lint and format
uv run ruff check .
uv run ruff format --check .
```

## Architecture

### Deep Agents Pattern

The framework uses filesystem-based configuration — not code — for agent behavior:

- `AGENTS.md` — loaded as persistent memory (system prompt) for the `ops_manager` via `MemoryMiddleware`
- `skills/<domain>/` — per-subagent skill directories loaded via `SkillsMiddleware`; each skill is a folder containing `SKILL.md` plus optional templates
- `skills/common/` — shared skills referenced by all subagents
- `subagents.yaml` — defines specialist subagents; loaded by `load_subagents()` helper (not native to deepagents). Mounted from ConfigMap for hot-reload on pod restart
- `templates/` — Jinja2 or markdown templates for ticket output (`TICKET.md.j2`, `output-kira.md`, `output-rocketchat.md`)

Built-in deepagents tools: `write_file`, `read_file`, `edit_file`, `ls`, `glob`, `grep`, `execute`, `task` (subagent delegation), `write_todos`.

### Agent Hierarchy

```
AAP2 webhook → athena service → ops_manager (main agent)
                                    ├── sre_ansible     (playbook/role/collection/credential issues)
                                    ├── sre_linux       (dnf/systemd/SELinux/filesystem/Satellite)
                                    └── sre_openshift   (pod/image/RBAC/operator/networking)
                                    
ops_manager produces TICKET.md → reviewer validates → informer routes to:
                                                        ├── kira (API)
                                                        └── rocket.chat (optional)
```

### Flow

1. AAP2 sends a webhook to Athena when a job fails
2. Athena retrieves job artifacts (stdout, events, metadata, template, related files) via `aap2_*` tools
3. Normalizes into an internal incident envelope and passes to `ops_manager`
4. `ops_manager` classifies the failure domain using the `error-classifier` skill
5. Delegates to one specialist SRE subagent (`sre_ansible`, `sre_linux`, or `sre_openshift`)
6. SRE subagent performs root-cause analysis, produces `TICKET.md`
7. `reviewer` validates ticket completeness, schema, actionability
8. `informer` routes to `kira` via API adapter and optionally to Rocket.Chat

### Custom Tools (small surface by design)

- `aap2_get_job`, `aap2_get_job_events`, `aap2_get_job_stdout`, `aap2_get_job_template`, `aap2_get_related_artifacts` — AAP2 Controller API
- `kira_create_ticket` — ticketing system adapter
- `rocketchat_post_message` — notification adapter
- `web_search` via Tavily (optional)

### Skills

Skills live in `skills/` (mountable PVC). Each is a folder with `SKILL.md`:

- `error-classifier` — classify failure domain, emit domain/confidence/rationale
- `analyze-ansible-failure`, `analyze-linux-failure`, `analyze-openshift-failure` — domain-specific analysis
- `create-ticket` — produce canonical `TICKET.md`
- `review-ticket` — validate required sections and coherence
- `output-to-kira` — map ticket into Kira API payload
- `output-to-rocket-chat` — format notification with ticket link

## Adding a New Subagent

1. Add entry to `subagents.yaml` with description, model, system_prompt, tools, skills
2. Add any new `@tool` functions in the service code
3. Register tool names in the `available_tools` dict inside `load_subagents()`
4. Create skill directory `skills/<domain>/` with subdirectories containing `SKILL.md`
5. Update `AGENTS.md` domain awareness section

## Adding a New Skill

1. Create `skills/<domain>/<skill-name>/SKILL.md`
2. Skills are auto-discovered by `SkillsMiddleware` — no code registration needed
3. Add the source path to the subagent's `skills:` array in `subagents.yaml`
4. Shared skills go in `skills/common/`

## Deployment

Single Python service in one container on OpenShift. Stateless pod with externalized config:
- `AGENTS.md` and `subagents.yaml` from ConfigMaps
- Credentials (AAP2, Kira, Rocket.Chat, Tavily) from Secrets
- `skills/` from PVC (add skills without rebuilding the image)

## Key Conventions

- Python 3.13 — always use `uv`, never `pip`
- Always use Pydantic V2 for structured outputs with OpenAI API
- Skills first: prefer skills over large tool sets to reduce context load
- Subagent models default to `anthropic:claude-sonnet-4-20250514`
- Keep the tool surface small — filesystem and skills do the heavy lifting
- `prd-athena.md` is the authoritative product requirements document

## Resources and References

- [LangChain Deep Agents repo](https://github.com/langchain-ai/deepagents.git) — framework source and `examples/` directory for implementation patterns
- [Introducing Deep Agents](https://blog.langchain.com/deep-agents/)
- [Doubling Down on Deep Agents](https://blog.langchain.com/doubling-down-on-deepagents/)
- [Using Skills with Deep Agents](https://blog.langchain.com/using-skills-with-deep-agents/)
- [Building Multi-Agent Applications with Deep Agents](https://blog.langchain.com/building-multi-agent-applications-with-deep-agents/)
