"""FastAPI application with lifespan for client initialization and webhook registration."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from athena.adapters.aap2 import AAP2Client
from athena.adapters.kira import KiraClient
from athena.adapters.rocketchat import RocketChatClient
from athena.config import Settings
from athena.routes import analyze, health, webhook

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize clients and register AAP2 webhook on startup."""
    # Load and validate configuration
    settings = Settings()

    # Configure MaaS gateway for LangChain (OpenAI-compatible endpoint)
    os.environ["OPENAI_API_BASE"] = settings.litellm_api_base_url
    os.environ["OPENAI_API_KEY"] = settings.litellm_virtual_key.get_secret_value()

    # Optional: Tavily for web search
    if settings.tavily_api_key:
        os.environ["TAVILY_API_KEY"] = settings.tavily_api_key.get_secret_value()

    # Initialize adapter clients
    aap2 = AAP2Client(
        base_url=settings.aap2_url,
        username=settings.aap2_username,
        password=settings.aap2_password.get_secret_value(),
        organization=settings.aap2_organization,
    )
    kira = KiraClient(
        base_url=settings.kira_url,
        api_key=settings.kira_api_key.get_secret_value(),
    )
    rocketchat = RocketChatClient(
        base_url=settings.rocketchat_url,
        auth_token=settings.rocketchat_api_auth_token.get_secret_value(),
        user_id=settings.rocketchat_api_user_id,
    )

    # Store in app state for route handlers
    app.state.settings = settings
    app.state.aap2 = aap2
    app.state.kira = kira
    app.state.rocketchat = rocketchat

    # Register webhook in AAP2 (idempotent)
    try:
        webhook_url = settings.athena_base_url or "http://athena:8080"
        target = f"{webhook_url.rstrip('/')}{settings.athena_webhook_path}"
        template_id = await aap2.register_webhook(target)
        logger.info("AAP2 webhook registered (template_id=%s)", template_id)
        health.set_ready(True)
    except Exception:
        logger.exception("Failed to register AAP2 webhook — readiness probe will fail")

    yield


app = FastAPI(
    title="Athena AIOps",
    description="Agentic AIOps service for AAP2 failure analysis",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(analyze.router)
