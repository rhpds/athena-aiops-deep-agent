"""Centralized configuration from environment variables."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All Athena configuration. Validated at startup — missing vars cause immediate failure."""

    model_config = {"env_prefix": "", "case_sensitive": False}

    # AAP2 Controller
    aap2_url: str
    aap2_username: str
    aap2_password: SecretStr
    aap2_organization: str

    # Kira ticketing system
    kira_url: str
    kira_api_key: SecretStr

    # Rocket.Chat
    rocketchat_url: str
    rocketchat_api_auth_token: SecretStr
    rocketchat_api_user_id: str
    rocketchat_channel: str = "support"

    # MaaS (LLM gateway) — env var names are litellm_* per provisioning system
    litellm_api_base_url: str
    litellm_virtual_key: SecretStr

    # Optional
    tavily_api_key: SecretStr | None = None

    # Athena service
    athena_webhook_path: str = "/api/v1/webhook/aap2"
    athena_base_url: str | None = None
