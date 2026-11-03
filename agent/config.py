from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv

Provider = Literal["openai", "anthropic", "gemini"]

load_dotenv()


@dataclass(frozen=True)
class Settings:
    ai_provider: Provider = "openai"
    state_path: str = "data/learner.db"
    max_history_messages: int = 24
    quality_gate: bool = False
    multi_agent: bool = False
    cross_validate: bool = False
    research_enabled: bool = False
    local_knowledge_path: str = "data/knowledge"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"
    cors_origins: str = ""
    openai_model: str | None = None
    anthropic_model: str | None = None
    gemini_model: str | None = None
    voice_provider: str = "openai"
    openai_stt_model: str | None = None
    openai_tts_model: str | None = None
    openai_tts_voice: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
        if provider not in {"openai", "anthropic", "gemini"}:
            raise ValueError("AI_PROVIDER must be one of: openai, anthropic, gemini")
        return cls(
            ai_provider=provider,  # type: ignore[arg-type]
            state_path=os.getenv("STATE_PATH", "data/learner.db"),
            max_history_messages=int(os.getenv("MAX_HISTORY_MESSAGES", "24")),
            quality_gate=os.getenv("QUALITY_GATE", "false").lower() == "true",
            multi_agent=os.getenv("MULTI_AGENT", "false").lower() == "true",
            cross_validate=os.getenv("CROSS_VALIDATE", "false").lower() == "true",
            research_enabled=os.getenv("RESEARCH_ENABLED", "false").lower() == "true",
            local_knowledge_path=os.getenv("LOCAL_KNOWLEDGE_PATH", "data/knowledge"),
            app_host=os.getenv("APP_HOST", "0.0.0.0"),
            app_port=int(os.getenv("APP_PORT", "8000")),
            log_level=os.getenv("LOG_LEVEL", "info"),
            cors_origins=os.getenv("CORS_ORIGINS", ""),
            openai_model=os.getenv("OPENAI_MODEL") or None,
            anthropic_model=os.getenv("ANTHROPIC_MODEL") or None,
            gemini_model=os.getenv("GEMINI_MODEL") or None,
            voice_provider=os.getenv("VOICE_PROVIDER", "openai").strip().lower(),
            openai_stt_model=os.getenv("OPENAI_STT_MODEL") or None,
            openai_tts_model=os.getenv("OPENAI_TTS_MODEL") or None,
            openai_tts_voice=os.getenv("OPENAI_TTS_VOICE") or None,
        )

    @property
    def data_dir(self) -> Path:
        return Path(self.state_path).parent

    def validate_voice_credentials(self) -> list[str]:
        """Missing env vars for the configured voice provider (openai only)."""
        if (self.voice_provider or "openai").strip().lower() != "openai":
            return [f"VOICE_PROVIDER={self.voice_provider!r} is not supported"]
        missing = []
        if not os.getenv("OPENAI_API_KEY"):
            missing.append("OPENAI_API_KEY")
        return missing

    def validate_provider_credentials(self, provider: str | None = None) -> list[str]:
        provider = provider or self.ai_provider
        key_name = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }[provider]
        model_name = {
            "openai": "OPENAI_MODEL",
            "anthropic": "ANTHROPIC_MODEL",
            "gemini": "GEMINI_MODEL",
        }[provider]
        missing = []
        if not os.getenv(key_name):
            missing.append(key_name)
        if not os.getenv(model_name):
            missing.append(model_name)
        return missing
