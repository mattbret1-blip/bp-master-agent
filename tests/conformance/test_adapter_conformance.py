"""Adapter conformance: every provider adapter satisfies the same contract.

Runs offline — no API keys, no network. An adapter whose SDK or credentials
are missing must fail fast with a clear error, never return half-initialized.
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adapters import AnthropicAdapter, GeminiAdapter, OpenAIAdapter
from agent.config import Settings
from agent.providers import build_adapter

ADAPTERS = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
    "gemini": GeminiAdapter,
}

SDK_MODULE = {
    "openai": "openai",
    "anthropic": "anthropic",
    "gemini": "google.genai",
}

REQUIRED_ENV = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


@pytest.mark.parametrize("name,cls", ADAPTERS.items())
def test_adapter_exposes_generate_structured(name, cls):
    params = [
        p for p in inspect.signature(cls.generate_structured).parameters if p != "self"
    ]
    assert params == ["system", "messages", "schema", "schema_name"], (
        f"{name}: generate_structured signature drifted: {params}"
    )


@pytest.mark.parametrize("name,cls", ADAPTERS.items())
def test_adapter_init_accepts_optional_model(name, cls):
    sig = inspect.signature(cls.__init__)
    assert "model" in sig.parameters, f"{name}: __init__ must accept a model kwarg"
    assert sig.parameters["model"].default is None


def test_build_adapter_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported provider"):
        build_adapter("bogus", Settings())


@pytest.mark.parametrize("name,cls", ADAPTERS.items())
def test_adapter_fails_fast_without_api_key(name, cls, monkeypatch):
    """With its SDK installed but the API key missing, construction must
    raise immediately instead of producing a broken client."""
    pytest.importorskip(SDK_MODULE[name])
    monkeypatch.delenv(REQUIRED_ENV[name], raising=False)
    with pytest.raises(KeyError):
        cls()
