"""Provider clients. Ollama is the MVP; Anthropic and OpenAI are implemented; Google Gemini
is served through its OpenAI-compatible endpoint (``google.py``, 12 Sep 2026)."""

from __future__ import annotations

from .base import ModelCallResult, ProviderClient


def get_provider(name: str, **kwargs) -> ProviderClient:
    """Factory mapping a provider name to a client instance."""
    name = name.lower()
    if name == "ollama":
        from .ollama import OllamaProvider

        return OllamaProvider(**kwargs)
    if name == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(**kwargs)
    if name == "openai":
        from .openai import OpenAIProvider

        return OpenAIProvider(**kwargs)
    if name in ("google", "gemini"):
        from .google import GoogleProvider

        return GoogleProvider(**kwargs)
    raise ValueError(f"unknown provider: {name!r}")


__all__ = ["ModelCallResult", "ProviderClient", "get_provider"]
