"""Voice in/out, tested offline with a fake audio adapter.

No API keys, no network: the OpenAI voice adapter is only checked for its
protocol shape and its fail-fast behavior, never for a live call.
"""
import inspect
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import main
from agent.audio import build_audio_adapter, guess_mime_type
from agent.config import Settings
from agent.voice import Transcript
from adapters.openai_voice import (
    DEFAULT_STT_MODEL,
    DEFAULT_TTS_MODEL,
    DEFAULT_TTS_VOICE,
    OpenAIVoiceAdapter,
)


class FakeAudioAdapter:
    """Deterministic stand-in for a real voice provider."""

    def __init__(self):
        self.transcribe_calls = []
        self.synthesize_calls = []

    def transcribe(self, audio_bytes, mime_type):
        self.transcribe_calls.append((audio_bytes, mime_type))
        return Transcript(text="Olá, tudo bem?", language="pt-BR")

    def synthesize(self, text, voice="default"):
        self.synthesize_calls.append((text, voice))
        return b"FAKEWAVBYTES"


class StubAgent:
    def opening_diagnostic(self):
        return ""

    def respond(self, text):
        raise AssertionError("respond should not be called in voice tests")


def _run_repl(monkeypatch, tmp_path, inputs, audio_adapter):
    monkeypatch.chdir(tmp_path)
    answers = iter(inputs)

    def fake_input(prompt=""):
        return next(answers)

    monkeypatch.setattr("builtins.input", fake_input)
    return main.repl(StubAgent(), audio_adapter=audio_adapter)


def test_openai_voice_adapter_exposes_protocol_methods():
    transcribe_params = [
        p for p in inspect.signature(OpenAIVoiceAdapter.transcribe).parameters if p != "self"
    ]
    assert transcribe_params == ["audio_bytes", "mime_type"]
    synth_params = inspect.signature(OpenAIVoiceAdapter.synthesize).parameters
    assert [p for p in synth_params if p != "self"] == ["text", "voice"]
    assert synth_params["voice"].default == "default"


def test_openai_voice_adapter_fails_fast_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        OpenAIVoiceAdapter()


def test_openai_voice_adapter_construction_uses_documented_defaults(monkeypatch):
    # Construction only builds the SDK client; no network call is made.
    # Proxy env vars are cleared because this sandbox's proxy setup trips
    # httpx's URL parsing at client-construction time (environment quirk,
    # not adapter behavior).
    for var in (
        "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
        "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
    ):
        monkeypatch.delenv(var, raising=False)
    adapter = OpenAIVoiceAdapter(api_key="test-key")
    assert adapter.stt_model == DEFAULT_STT_MODEL == "gpt-4o-transcribe"
    assert adapter.tts_model == DEFAULT_TTS_MODEL == "gpt-4o-mini-tts"
    assert adapter.tts_voice == DEFAULT_TTS_VOICE == "alloy"


def test_factory_selects_openai(monkeypatch):
    seen = {}

    class FakeVoice:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    monkeypatch.setattr("agent.audio.OpenAIVoiceAdapter", FakeVoice)
    build_audio_adapter(Settings(voice_provider="openai", openai_tts_voice="nova"))
    assert seen["tts_voice"] == "nova"


def test_factory_rejects_unknown_provider():
    with pytest.raises(ValueError, match="Unsupported voice provider"):
        build_audio_adapter(Settings(voice_provider="acme"))


def test_factory_fails_fast_without_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        build_audio_adapter(Settings(voice_provider="openai"))


def test_guess_mime_type():
    assert guess_mime_type("recording.wav") == "audio/wav"
    assert guess_mime_type("recording.mp3") == "audio/mpeg"
    assert guess_mime_type("recording.webm") == "audio/webm"
    assert guess_mime_type("recording.unknown-ext") == "application/octet-stream"


def test_cli_say_writes_wav_file(monkeypatch, tmp_path, capsys):
    fake = FakeAudioAdapter()
    code = _run_repl(monkeypatch, tmp_path, ["/say Olá, tudo bem?", "/quit"], fake)
    assert code == 0
    assert fake.synthesize_calls == [("Olá, tudo bem?", "default")]
    written = list(tmp_path.glob("say-*.wav"))
    assert len(written) == 1
    assert written[0].read_bytes() == b"FAKEWAVBYTES"
    assert written[0].name in capsys.readouterr().out


def test_cli_transcribe_prints_transcript(monkeypatch, tmp_path, capsys):
    (tmp_path / "rec.wav").write_bytes(b"FAKEAUDIO")
    fake = FakeAudioAdapter()
    code = _run_repl(monkeypatch, tmp_path, ["/transcribe rec.wav", "/quit"], fake)
    assert code == 0
    assert fake.transcribe_calls == [(b"FAKEAUDIO", "audio/wav")]
    out = capsys.readouterr().out
    assert "Olá, tudo bem?" in out


def test_cli_voice_commands_degrade_gracefully(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    code = _run_repl(
        monkeypatch, tmp_path, ["/say Olá", "/quit"], audio_adapter=None
    )
    assert code == 0
    err = capsys.readouterr().err
    assert "Voz indisponível" in err
    assert "OPENAI_API_KEY" in err


def test_transcript_defaults_to_pt_br():
    assert Transcript(text="Oi").language == "pt-BR"
    assert Transcript(text="Oi").confidence is None
