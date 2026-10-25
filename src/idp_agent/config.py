"""Runtime configuration, read from environment variables (see ``.env.example``)."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "claude-sonnet-5-5"
LLM_PROVIDERS = ("none", "anthropic")


class ConfigError(ValueError):
    """Raised when a configuration value is invalid."""


@dataclass(frozen=True)
class Settings:
    """Immutable settings object passed explicitly through the pipeline."""

    output_dir: Path = Path("output")
    llm_provider: str = "none"
    llm_model: str = DEFAULT_MODEL
    anthropic_api_key: str | None = field(default=None, repr=False)
    max_retries: int = 3
    retry_backoff: float = 0.5
    ocr_lang: str = "eng+fra"
    min_confidence: float = 0.6
    max_upload_mb: int = 10

    def __post_init__(self) -> None:
        if self.llm_provider not in LLM_PROVIDERS:
            raise ConfigError(
                f"IDP_LLM_PROVIDER must be one of {LLM_PROVIDERS}, got '{self.llm_provider}'"
            )
        if self.max_retries < 1:
            raise ConfigError("IDP_MAX_RETRIES must be >= 1")
        if not 0.0 <= self.min_confidence <= 1.0:
            raise ConfigError("IDP_MIN_CONFIDENCE must be between 0 and 1")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, **overrides: Any) -> Settings:
        """Build settings from ``env`` (defaults to ``os.environ``); ``overrides`` win."""
        source = os.environ if env is None else env

        def read(name: str, default: Any, cast: type) -> Any:
            raw = source.get(name)
            if raw is None or raw == "":
                return default
            try:
                return cast(raw)
            except ValueError as exc:
                raise ConfigError(f"{name}={raw!r} is not a valid {cast.__name__}") from exc

        values: dict[str, Any] = {
            "output_dir": Path(read("IDP_OUTPUT_DIR", "output", str)),
            "llm_provider": read("IDP_LLM_PROVIDER", "none", str).lower(),
            "llm_model": read("IDP_LLM_MODEL", DEFAULT_MODEL, str),
            "anthropic_api_key": read("ANTHROPIC_API_KEY", None, str),
            "max_retries": read("IDP_MAX_RETRIES", 3, int),
            "retry_backoff": read("IDP_RETRY_BACKOFF", 0.5, float),
            "ocr_lang": read("IDP_OCR_LANG", "eng+fra", str),
            "min_confidence": read("IDP_MIN_CONFIDENCE", 0.6, float),
            "max_upload_mb": read("IDP_MAX_UPLOAD_MB", 10, int),
        }
        values.update({k: v for k, v in overrides.items() if v is not None})
        return cls(**values)

    def with_updates(self, **changes: Any) -> Settings:
        return replace(self, **changes)
