"""Deep Agents pipeline — creates and runs the ops_manager agent.

Wires together:
- AGENTS.md as persistent memory (ops_manager persona)
- subagents.yaml as specialist SRE subagent definitions
- skills/ directories loaded per-subagent via SkillsMiddleware
- FilesystemBackend for incident context and ticket artifacts
"""

import json
import logging
import os
from pathlib import Path

import yaml
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from athena.agents.tools import web_search
from athena.config import Settings
from athena.models import IncidentEnvelope, TicketPayload

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent.parent.parent  # repo root


def load_subagents(config_path: Path) -> list[dict]:
    """Load subagent definitions from YAML and resolve tool references."""
    available_tools = {
        "web_search": web_search,
    }

    with open(config_path) as f:
        config = yaml.safe_load(f)

    subagents = []
    for name, spec in config.items():
        subagent = {
            "name": name,
            "description": spec["description"],
            "system_prompt": spec["system_prompt"],
        }
        if "model" in spec:
            # Strip provider prefix (e.g. "openai:claude-sonnet-4-6" -> "claude-sonnet-4-6")
            model_name = spec["model"].split(":")[-1] if ":" in spec["model"] else spec["model"]
            subagent["model"] = _make_maas_model(model_name)
        if "tools" in spec:
            subagent["tools"] = [available_tools[t] for t in spec["tools"]]
        if "skills" in spec:
            subagent["skills"] = spec["skills"]
        subagents.append(subagent)

    return subagents


def _make_maas_model(model_name: str = "claude-sonnet-4-6") -> ChatOpenAI:
    """Create a ChatOpenAI instance pointing at the MaaS gateway.

    Uses the classic Chat Completions API (not the newer Responses API)
    for compatibility with LiteLLM-based MaaS gateways.
    """
    # Strip provider prefix (e.g. "openai/claude-sonnet-4-6" -> "claude-sonnet-4-6")
    bare_name = model_name.split("/")[-1] if "/" in model_name else model_name
    bare_name = bare_name.split(":")[-1] if ":" in bare_name else bare_name
    return ChatOpenAI(
        model=bare_name,
        openai_api_base=os.environ.get("OPENAI_API_BASE"),
        openai_api_key=os.environ.get("OPENAI_API_KEY"),
        use_responses_api=False,
        request_timeout=90,  # fail fast on hanging MaaS connections
        max_retries=0,  # outer retry loop in webhook.py handles pipeline-level retries
    )


def create_ops_manager(settings: Settings):
    """Create the ops_manager Deep Agent configured by filesystem files.

    The MaaS gateway is configured via environment variables set in app.py lifespan.
    """
    return create_deep_agent(
        model=_make_maas_model(os.environ.get("OPS_MANAGER_MODEL", "claude-sonnet-4-6")),
        memory=["./AGENTS.md"],
        tools=[],
        subagents=load_subagents(PROJECT_DIR / "subagents.yaml"),
        backend=FilesystemBackend(root_dir=PROJECT_DIR),
    )


async def run_pipeline(envelope: IncidentEnvelope, settings: Settings) -> TicketPayload:
    """Run the full agent pipeline on an incident.

    1. Write incident context to filesystem
    2. Invoke ops_manager agent
    3. Parse structured TicketPayload from agent output
    """
    # Write incident context for agents to read
    incident_path = PROJECT_DIR / "incident.json"
    incident_path.write_text(envelope.model_dump_json(indent=2))

    # Create and run the agent
    agent = create_ops_manager(settings)

    incident_summary = (
        f"A failed AAP2 job requires analysis.\n\n"
        f"Job: {envelope.job.name} (ID: {envelope.job.id})\n"
        f"Template: {envelope.job.template_name}\n"
        f"Project: {envelope.job.project}\n"
        f"Inventory: {envelope.job.inventory}\n\n"
        f"Error excerpt:\n{envelope.artifacts.error_excerpt}\n\n"
        f"Read incident.json for full context. "
        f"Classify the failure, delegate to the right specialist, "
        f"have the reviewer validate, and return a TicketPayload JSON."
    )

    final_message = None
    async for chunk in agent.astream(
        {"messages": [("user", incident_summary)]},
        config={"configurable": {"thread_id": f"incident-{envelope.event_id}"}},
        stream_mode="values",
    ):
        if "messages" in chunk:
            messages = chunk["messages"]
            if messages:
                last = messages[-1]
                if isinstance(last, AIMessage) and last.content:
                    final_message = last

    if not final_message:
        raise RuntimeError("Agent pipeline produced no output")

    # Extract structured output from the final message
    content = final_message.content
    if isinstance(content, list):
        text_parts = [
            p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text"
        ]
        content = "\n".join(text_parts)

    # Parse JSON from the agent response
    ticket_data = _extract_json(content)
    ticket = TicketPayload(**ticket_data)

    # Inject model metadata if the agent reported its name
    if ticket.agent_name and not ticket.model_name:
        try:
            with open(PROJECT_DIR / "subagents.yaml") as f:
                all_agents = yaml.safe_load(f)
            agent_spec = all_agents.get(ticket.agent_name, {})
            if "model" in agent_spec:
                raw = agent_spec["model"]
                bare = raw.split("/")[-1] if "/" in raw else raw
                bare = bare.split(":")[-1] if ":" in bare else bare
                ticket.model_name = bare
        except Exception:
            pass

    return ticket


def _extract_json(text: str) -> dict:
    """Extract a JSON object from agent text output.

    Handles both raw JSON and JSON inside markdown code blocks.
    """
    import re

    # Try markdown code block first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Try raw JSON
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])

    raise ValueError(f"Could not extract JSON from agent output: {text[:200]}")
