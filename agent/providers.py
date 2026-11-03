from __future__ import annotations

from adapters import AnthropicAdapter, GeminiAdapter, OpenAIAdapter
from .config import Provider, Settings


def build_adapter(provider: Provider, settings: Settings | None = None):
    settings = settings or Settings.from_env()
    if provider == "openai":
        return OpenAIAdapter(model=settings.openai_model)
    if provider == "anthropic":
        return AnthropicAdapter(model=settings.anthropic_model)
    if provider == "gemini":
        return GeminiAdapter(model=settings.gemini_model)
    raise ValueError(f"Unsupported provider: {provider}")
