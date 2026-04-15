"""Tests for athena.config."""

import pytest
from pydantic import ValidationError

from athena.config import Settings


def _minimal_env() -> dict[str, str]:
    """Minimal valid env vars for Settings."""
    return {
        "aap2_url": "https://aap2.example.com",
        "aap2_username": "admin",
        "aap2_password": "secret",
        "aap2_organization": "org-test",
        "kira_url": "https://kira.example.com",
        "kira_api_key": "key-123",
        "rocketchat_url": "https://chat.example.com",
        "rocketchat_api_auth_token": "token-abc",
        "rocketchat_api_user_id": "user-123",
        "litellm_api_base_url": "https://maas.example.com/v1",
        "litellm_virtual_key": "sk-test",
    }


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch):
    env = _minimal_env()
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    settings = Settings()
    assert settings.aap2_url == "https://aap2.example.com"
    assert settings.aap2_password.get_secret_value() == "secret"
    assert settings.rocketchat_channel == "support"
    assert settings.tavily_api_key is None


def test_settings_fails_on_missing_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("aap2_url", "https://aap2.example.com")
    with pytest.raises(ValidationError):
        Settings()


def test_settings_optional_tavily(monkeypatch: pytest.MonkeyPatch):
    env = _minimal_env()
    env["tavily_api_key"] = "tvly-test"
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    settings = Settings()
    assert settings.tavily_api_key.get_secret_value() == "tvly-test"
