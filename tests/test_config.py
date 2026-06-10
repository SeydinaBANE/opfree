import pytest
from pydantic import ValidationError

from incident_copilot.config import Settings
from incident_copilot.log import configure_logging

_SETTINGS_ENV_KEYS = [
    "LLM_PROVIDER",
    "LLM_MODEL",
    "ANTHROPIC_API_KEY",
    "AWS_REGION",
    "AWS_PROFILE",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_REGION",
    "MAX_AGENT_ITERATIONS",
    "MAX_TOTAL_TOKENS",
    "AGENT_TIMEOUT_SECONDS",
    "LOG_LEVEL",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _SETTINGS_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_settings_defaults() -> None:
    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.llm_provider == "anthropic"
    assert s.llm_model == "claude-sonnet-4-6"
    assert s.max_agent_iterations == 15
    assert s.max_total_tokens == 200_000
    assert s.agent_timeout_seconds == 300
    assert s.log_level == "INFO"


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "bedrock")
    monkeypatch.setenv("MAX_AGENT_ITERATIONS", "5")

    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert s.llm_provider == "bedrock"
    assert s.max_agent_iterations == 5


def test_settings_invalid_provider_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "unknown")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_anthropic_api_key_is_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    s = Settings(_env_file=None)  # type: ignore[call-arg]

    assert "sk-ant-test" not in repr(s)
    assert s.anthropic_api_key.get_secret_value() == "sk-ant-test"


def test_configure_logging_info_does_not_raise() -> None:
    configure_logging("INFO")


def test_configure_logging_debug_does_not_raise() -> None:
    configure_logging("DEBUG")
