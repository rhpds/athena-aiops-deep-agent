# MLflow Showroom Bonus Module — Design Spec

**Date**: 2026-06-01
**Author**: Tony Kay / Claude
**Status**: Draft
**Target file**: `showroom-summit-2026-lb2465-agentic-ai-ops/content/modules/ROOT/pages/11-bonus-mlflow-observability.adoc`

## Context

The showroom lab has a LangFuse bonus module (`09-module-07-tracing.adoc`) that walks students through agent pipeline traces. MLflow has been deployed alongside LangFuse as a dual tracing backend — `mlflow.langchain.autolog()` captures every LLM call, tool invocation, and subagent delegation automatically.

This spec defines a standalone MLflow bonus module that introduces MLflow, then guides students through the trace UI to understand what their agent pipeline actually does when it analyzes a failure.

## Design Decisions

- **Standalone**: No dependency on the LangFuse module. MLflow may eventually become the primary tracing module with LangFuse as the backup bonus.
- **No "trigger a failure" step**: Students have traces from earlier modules. Avoids redundant exercise setup.
- **Brief MLflow intro**: An admonition box (not a full section) positions MLflow's breadth without derailing into data science territory. The audience is SREs and platform engineers.
- **Details & Timeline is the core**: The Summary view gets a quick orientation pass, but the guided walkthrough of the timeline — mapping spans to agent behavior — is the main educational content.
- **Subagent lifecycle is the highlight**: The nested `task` delegation span is where students see the Deep Agents pattern through the observability lens.
- **OAuth SSO login**: MLflow uses OpenShift OAuth proxy, so login is seamless if already authenticated. Falls back to `{user}`/`{password}`.

## Module Structure

### 1. Intro + Learning Objectives (~15 lines)

**Narrative hook**: "Throughout this workshop, you've waited a few minutes for tickets to appear after triggering failures. Where did that time go? What was the agent doing? In this module, you'll find out."

**Learning objectives**:
- Navigate the MLflow trace UI to understand agent execution flow
- Read the Details & Timeline view to identify where time is spent
- Follow a subagent delegation from ops_manager through specialist analysis to reviewer
- Understand the cost profile of an agentic pipeline (LLM reasoning vs. tool execution)

### 2. What is MLflow? (admonition box, ~8 lines)

A `[NOTE]` or `[TIP]` admonition with title "About MLflow":
- MLflow is an open-source platform for the full ML/AI lifecycle — experiment tracking, model registry, model serving, evaluation, and tracing
- Originally built for traditional ML, MLflow has expanded to cover LLM and agentic AI workflows
- Athena uses MLflow's LangChain integration (`mlflow.langchain.autolog()`) to automatically capture every pipeline execution
- "We'll focus on tracing here, but the same platform can track how your agent's performance evolves as you change models, skills, or architecture"

### 3. Open MLflow and Find a Trace (~25 lines)

Steps:
1. Open the **MLflow** tab in the top navigation bar
2. OAuth SSO note: if prompted, log in with `{user}` / `{password}`
3. You should see your experiment (named after your namespace, e.g. `user-xxxxx-agentic`)
4. Brief orientation of the experiment view: list of runs on the left, each run = one incident analysis by Athena
5. Click on a recent run to open it
6. Note the **Summary** tab: trace ID, total latency, session ID
7. "The summary tells you *that* something happened and how long it took. To see *what* happened, switch to **Details & Timeline**."

### 4. Details & Timeline — Following the Agent Lifecycle (~70 lines, core section)

This is the main educational content. Guide students through the trace top-to-bottom, mapping each span to agent behavior.

#### 4a. Reading the timeline

- The left panel shows a **Trace breakdown** — a tree of nested spans
- Blue bars = time spent. Wider = longer.
- Spans are nested: a `model` call contains a `ChatOpenAI` call which may trigger `tools` calls
- The right panel shows **Inputs/Outputs** for the selected span

#### 4b. The ops_manager's first moves

Walk through the first few spans:
- **First `model` call** (~2-3s): ops_manager receives the incident summary, reads its system prompt (AGENTS.md), and decides what to do first
- **`tools` → `read_file`**: Reading `incident.json` — the full incident context
- **Second `model` call**: After reading the incident, ops_manager loads the error-classifier skill and classifies the failure domain
- Point out the Inputs panel: "Click a model span to see the actual messages — the system prompt, the user message, and the assistant's response including any tool_calls"

#### 4c. The specialist comes to life

The most interesting part of the trace:
- **`tools` → `read_file`**: The specialist loading its domain skill (e.g., `skills/analyze-linux-failure/SKILL.md`)
- **`model` calls**: Multiple reasoning steps as the specialist analyzes the failure
- **`tools` → `glob`, `grep`**: The specialist searching for patterns in the incident data
- "This is the Deep Agents pattern in action — a fresh agent with fresh context, loaded with domain-specific skills, reasoning about one problem"
- Point out: "The specialist's spans are *nested inside* the `task` tool call. This is how delegation works — the manager invokes `task`, which creates the specialist, which runs its own ReAct loop"

#### 4d. The reviewer

- After the specialist returns, another `task` delegation appears — the reviewer
- "Notice the model name — this is a different, cheaper model (Haiku). The reviewer validates rather than analyzes, so a faster model is appropriate"
- The reviewer's spans are shorter — fewer reasoning steps, no tool calls for skill loading

#### 4e. Where is the time?

Wrap up the walkthrough with the key insight:
- "Look at the blue bars. Where is the pipeline spending its time?"
- Model calls (LLM reasoning) dominate — seconds each
- Tool calls (read_file, glob, grep) are milliseconds
- "The cost of an agentic pipeline is almost entirely LLM inference. Tool execution is nearly free. This matters when you're choosing models — a 2x faster model cuts your pipeline time nearly in half"

### 5. Inputs and Outputs — What the Agent Actually Said (~25 lines)

Brief section on using the right panel:
- Click any `model` span to see Inputs (the messages sent to the LLM) and Outputs (the response)
- The system message shows the agent's persona and loaded skills
- The assistant response shows tool_calls — the agent's decision about what to do next
- The final model call's output contains the TicketPayload JSON
- "This is the audit trail. Every decision the agent made — which specialist to call, what evidence to cite, what risk level to assign — is recorded here"

### 6. Summary + Forward Look (~15 lines)

What you learned:
- MLflow captures the full execution trace of every pipeline run automatically
- The Details & Timeline view maps directly to the agent lifecycle: classify → delegate → analyze → review → output
- Most pipeline time and cost is in LLM reasoning, not tool execution
- The trace is a complete audit trail — every agent decision is recorded with its inputs and outputs

Forward look (2-3 sentences):
- "As your agent evolves — new specialists, different models, additional skills — MLflow tracks how those changes affect latency, token usage, and analysis quality"
- "The same experiment view can compare runs across different configurations, helping you optimize the cost/quality tradeoff"

## Nav Integration

Add to `nav.adoc` under the `.Bonus` section:
```
* xref:11-bonus-mlflow-observability.adoc[Observability with MLflow]
```

## Showroom Conventions

Per project conventions:
- `role="execute"` on source blocks for copy button
- `link=self` (no `window=blank`) for lightbox popout on images
- No trailing period after credential examples
- No blank line after `====` admonition delimiter
- Pre-render Mermaid as SVGs for split-panel readability (not applicable here — no diagrams planned)
- `{user}` / `{password}` for credentials, not `{guid}`

## Out of Scope

- Screenshots embedded in the module (students follow along in their own MLflow instance)
- LangFuse comparison or cross-reference
- MLflow model registry, serving, or evaluation deep dive
- Experiment comparison across model configs (potential future module)
- Any code changes to Athena or deployer roles

## Estimated Length

~160-180 lines of AsciiDoc, similar to the LangFuse module but with richer walkthrough content in the Details & Timeline section.
