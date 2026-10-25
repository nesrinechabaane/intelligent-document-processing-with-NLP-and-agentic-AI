from __future__ import annotations

import pytest

from idp_agent.config import ConfigError, Settings


def test_defaults_are_offline() -> None:
    settings = Settings.from_env({})
    assert settings.llm_provider == "none"
    assert settings.max_retries == 3


def test_env_values_are_parsed() -> None:
    env = {"IDP_MAX_RETRIES": "5", "IDP_LLM_PROVIDER": "Anthropic", "IDP_OUTPUT_DIR": "res"}
    settings = Settings.from_env(env)
    assert settings.max_retries == 5
    assert settings.llm_provider == "anthropic"
    assert str(settings.output_dir) == "res"


def test_overrides_win_but_none_is_ignored() -> None:
    settings = Settings.from_env({"IDP_MAX_RETRIES": "5"}, max_retries=2, llm_provider=None)
    assert settings.max_retries == 2
    assert settings.llm_provider == "none"


@pytest.mark.parametrize(
    "env",
    [
        {"IDP_MAX_RETRIES": "many"},
        {"IDP_MAX_RETRIES": "0"},
        {"IDP_LLM_PROVIDER": "skynet"},
        {"IDP_MIN_CONFIDENCE": "2"},
    ],
)
def test_invalid_values_raise(env: dict[str, str]) -> None:
    with pytest.raises(ConfigError):
        Settings.from_env(env)


def test_api_key_is_not_in_repr() -> None:
    settings = Settings(anthropic_api_key="sk-secret")
    assert "sk-secret" not in repr(settings)
