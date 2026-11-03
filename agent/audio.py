from __future__ import annotations

import mimetypes

from adapters import OpenAIVoiceAdapter
from .config import Settings


# mimetypes reports .wav as audio/x-wav on some systems, and .webm as
# video/webm; providers expect the canonical audio types, so normalize.
_MIME_ALIASES = {
    "audio/x-wav": "audio/wav",
    "video/webm": "audio/webm",
}


def guess_mime_type(filename: str) -> str:
    """Best-effort MIME type for an uploaded/recorded audio file."""
    mime, _ = mimetypes.guess_type(filename)
    if mime and (mime.startswith("audio/") or mime in _MIME_ALIASES):
        return _MIME_ALIASES.get(mime, mime)
    return "application/octet-stream"


def build_audio_adapter(settings: Settings | None = None):
    """Build the configured voice adapter.

    Only ``openai`` is supported today. Anything else raises a clear
    ``ValueError`` rather than silently falling back to an invented
    provider implementation.
    """
    settings = settings or Settings.from_env()
    provider = (settings.voice_provider or "openai").strip().lower()
    if provider == "openai":
        return OpenAIVoiceAdapter(
            stt_model=settings.openai_stt_model,
            tts_model=settings.openai_tts_model,
            tts_voice=settings.openai_tts_voice,
        )
    raise ValueError(
        f"Unsupported voice provider: {provider!r}. "
        "Set VOICE_PROVIDER=openai (the only voice provider implemented)."
    )
