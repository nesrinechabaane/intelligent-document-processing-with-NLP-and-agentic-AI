"""Minimal LLM abstraction.

The agent only needs ``complete(system, prompt) -> str``. Keeping the interface this
small makes it trivial to fake in tests and to swap providers.
"""

from __future__ import annotations

from typing import Protocol

from .config import Settings


class LLMError(RuntimeError):
    """Raised when the LLM provider cannot be used or returns an error."""


class LLMClient(Protocol):
    def complete(self, system: str, prompt: str) -> str:  # pragma: no cover - protocol
        ...


class AnthropicClient:
    """Thin wrapper around the official ``anthropic`` SDK (optional dependency)."""

    def __init__(self, api_key: str, model: str, max_tokens: int = 1024) -> None:
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError("Install the LLM extra: pip install 'idp-agent[llm]'") from exc
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    def complete(self, system: str, prompt: str) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # SDK raises several error types; normalise them
            raise LLMError(f"LLM request failed: {exc}") from exc
        parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        return "".join(parts)


def build_llm(settings: Settings) -> LLMClient | None:
    """Return the configured client, or ``None`` when running fully offline."""
    if settings.llm_provider == "none":
        return None
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is required when IDP_LLM_PROVIDER=anthropic")
        return AnthropicClient(settings.anthropic_api_key, settings.llm_model)
    raise LLMError(f"Unsupported provider '{settings.llm_provider}'")
