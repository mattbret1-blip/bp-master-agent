"""Voice web endpoints, tested offline with a fake audio adapter.

The fake is injected by monkeypatching the factory; no provider key or
network is involved. The unconfigured cases prove the endpoints fail
closed with 503 instead of crashing the app.
"""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import web.app as web_app
from agent.voice import Transcript
from web.app import create_app


class FakeAudioAdapter:
    def __init__(self):
        self.transcribe_calls = []
        self.synthesize_calls = []

    def transcribe(self, audio_bytes, mime_type):
        self.transcribe_calls.append((audio_bytes, mime_type))
        return Transcript(text="Olá, tudo bem?", language="pt-BR")

    def synthesize(self, text, voice="default"):
        self.synthesize_calls.append((text, voice))
        return b"FAKEWAVBYTES"


@pytest.fixture
def voice_client(monkeypatch):
    """An app whose voice factory returns the fake; dummy key satisfies validation."""
    fake = FakeAudioAdapter()
    monkeypatch.setenv("OPENAI_API_KEY", "dummy-key-for-tests")
    monkeypatch.setattr(web_app, "build_audio_adapter", lambda settings: fake)
    client = TestClient(create_app(), raise_server_exceptions=False)
    return client, fake


def test_voice_transcribe(voice_client):
    client, fake = voice_client
    response = client.post(
        "/voice/transcribe",
        files={"file": ("rec.wav", b"FAKEAUDIO", "audio/wav")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["text"] == "Olá, tudo bem?"
    assert body["language"] == "pt-BR"
    assert fake.transcribe_calls == [(b"FAKEAUDIO", "audio/wav")]


def test_voice_transcribe_empty_file_is_400(voice_client):
    client, _ = voice_client
    response = client.post(
        "/voice/transcribe", files={"file": ("empty.wav", b"", "audio/wav")}
    )
    assert response.status_code == 400


def test_voice_synthesize_returns_wav(voice_client):
    client, fake = voice_client
    response = client.post("/voice/synthesize", json={"text": "Olá, tudo bem?"})
    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/wav"
    assert response.content == b"FAKEWAVBYTES"
    assert fake.synthesize_calls == [("Olá, tudo bem?", "default")]


def test_voice_synthesize_empty_text_is_400(voice_client):
    client, _ = voice_client
    response = client.post("/voice/synthesize", json={"text": "   "})
    assert response.status_code == 400


def test_voice_endpoints_unconfigured_are_503(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    client = TestClient(create_app(), raise_server_exceptions=False)
    transcribe = client.post(
        "/voice/transcribe", files={"file": ("rec.wav", b"FAKEAUDIO", "audio/wav")}
    )
    assert transcribe.status_code == 503
    assert "OPENAI_API_KEY" in transcribe.json()["detail"]
    synthesize = client.post("/voice/synthesize", json={"text": "Olá"})
    assert synthesize.status_code == 503
