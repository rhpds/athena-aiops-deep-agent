FROM python:3.13-slim AS builder

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml ./
RUN uv sync --no-dev --no-install-project

# Copy application code
COPY athena/ athena/
COPY AGENTS.md subagents.yaml ./
COPY skills/ skills/
COPY skills/ skills-default/
COPY templates/ templates/

# Install the project itself
RUN uv sync --no-dev

FROM python:3.13-slim

# Non-root user for OpenShift compatibility
RUN useradd --create-home --uid 1001 athena
USER 1001
WORKDIR /app

# Copy installed venv and app from builder
COPY --from=builder --chown=1001:1001 /app /app

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

CMD ["uvicorn", "athena.app:app", "--host", "0.0.0.0", "--port", "8080"]
