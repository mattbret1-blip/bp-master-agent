from __future__ import annotations

import os

from agent.voice import Transcript

# Defaults are the current OpenAI audio models; override with
# OPENAI_STT_MODEL / OPENAI_TTS_MODEL / OPENAI_TTS_VOICE.
DEFAULT_STT_MODEL = "gpt-4o-transcribe"
DEFAULT_TTS_MODEL = "gpt-4o-mini-tts"
DEFAULT_TTS_VOICE = "alloy"

_MIME_TO_SUFFIX = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/flac": "flac",
    "audio/mp4": "m4a",
    "audio/x-m4a": "m4a",
}


class OpenAIVoiceAdapter:
    """Speech-to-text and text-to-speech via the OpenAI audio APIs.

    Implements the :class:`agent.voice.AudioAdapter` protocol. The adapter
    fails fast at construction when ``OPENAI_API_KEY`` is missing so a
    half-initialized voice path can never silently swallow a request.

    Live calls were NOT tested in this environment (no provider API keys);
    see README.md. All automated tests run against a fake adapter.
    """

    def __init__(self, stt_model=None, tts_model=None, tts_voice=None, api_key=None):
        from openai import OpenAI

        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Set it in .env before using voice."
            )
        self.client = OpenAI(api_key=key)
        self.stt_model = stt_model or os.getenv("OPENAI_STT_MODEL") or DEFAULT_STT_MODEL
        self.tts_model = tts_model or os.getenv("OPENAI_TTS_MODEL") or DEFAULT_TTS_MODEL
        self.tts_voice = tts_voice or os.getenv("OPENAI_TTS_VOICE") or DEFAULT_TTS_VOICE

    def transcribe(self, audio_bytes: bytes, mime_type: str) -> Transcript:
        if not audio_bytes:
            raise ValueError("transcribe received empty audio bytes")
        suffix = _MIME_TO_SUFFIX.get((mime_type or "").lower(), "wav")
        response = self.client.audio.transcriptions.create(
            model=self.stt_model,
            file=(f"input.{suffix}", audio_bytes),
            language="pt",
        )
        return Transcript(text=response.text, language="pt-BR")

    def synthesize(self, text: str, voice: str = "default") -> bytes:
        if not text or not text.strip():
            raise ValueError("synthesize received empty text")
        chosen = self.tts_voice if voice in (None, "default") else voice
        response = self.client.audio.speech.create(
            model=self.tts_model,
            voice=chosen,
            input=text,
            response_format="wav",
        )
        return bytes(response.content)
