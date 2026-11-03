from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol, Optional

@dataclass
class Transcript:
    text: str
    language: str = "pt-BR"
    confidence: Optional[float] = None
    duration_ms: Optional[int] = None

class AudioAdapter(Protocol):
    def transcribe(self, audio_bytes: bytes, mime_type: str) -> Transcript: ...
    def synthesize(self, text: str, voice: str = "default") -> bytes: ...
