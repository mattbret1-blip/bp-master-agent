from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from agent.audio import build_audio_adapter, guess_mime_type
from agent.config import Settings
from agent.core import BrazilianPortugueseAgent
from agent.providers import build_adapter


def make_agent(provider: str | None = None) -> BrazilianPortugueseAgent:
    settings = Settings.from_env()
    chosen = provider or settings.ai_provider
    missing = settings.validate_provider_credentials(chosen)
    if missing:
        raise RuntimeError(
            f"Missing configuration for {chosen}: {', '.join(missing)}. "
            "Set those values in .env before starting the agent."
        )
    return BrazilianPortugueseAgent(
        build_adapter(chosen, settings),
        chosen,
    )


def print_json(value) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def _get_audio_adapter(audio_adapter, settings):
    """Lazy voice-adapter resolution so text-only sessions never pay for it.

    Tests inject a fake adapter; production builds the configured one on
    first voice command and reports a clear error when unconfigured.
    """
    if audio_adapter is not None:
        return audio_adapter
    return build_audio_adapter(settings)


def _cmd_say(text, audio_adapter, settings):
    adapter = _get_audio_adapter(audio_adapter, settings)
    audio = adapter.synthesize(text)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    filename = f"say-{stamp}.wav"
    Path(filename).write_bytes(audio)
    return filename


def _cmd_transcribe(path, audio_adapter, settings):
    adapter = _get_audio_adapter(audio_adapter, settings)
    data = Path(path).read_bytes()
    transcript = adapter.transcribe(data, guess_mime_type(path))
    return transcript


def repl(agent: BrazilianPortugueseAgent, audio_adapter=None, settings=None) -> int:
    opening = agent.opening_diagnostic()
    if opening:
        print(opening)
    print("\nCommands: /status /next /export /reset /say <text> /transcribe <audio-file> /quit")
    while True:
        try:
            text = input("\nVocê> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not text:
            continue
        if text == "/quit":
            return 0
        if text == "/status":
            print_json(agent.status())
            continue
        if text == "/next":
            print_json(agent.next_action())
            continue
        if text == "/export":
            print_json(agent.export())
            continue
        if text == "/reset":
            agent.reset()
            print("Estado reiniciado.")
            opening = agent.opening_diagnostic()
            if opening:
                print(opening)
            continue
        if text.startswith("/say "):
            spoken = text[len("/say "):].strip()
            if not spoken:
                print("Uso: /say <texto>", file=sys.stderr)
                continue
            try:
                filename = _cmd_say(spoken, audio_adapter, settings)
                print(f"Áudio salvo em: {filename}")
            except Exception as exc:
                print(f"Voz indisponível: {exc}", file=sys.stderr)
            continue
        if text.startswith("/transcribe "):
            path = text[len("/transcribe "):].strip()
            if not path:
                print("Uso: /transcribe <arquivo-de-áudio>", file=sys.stderr)
                continue
            try:
                transcript = _cmd_transcribe(path, audio_adapter, settings)
                print(f"Transcrição ({transcript.language}): {transcript.text}")
            except Exception as exc:
                print(f"Voz indisponível: {exc}", file=sys.stderr)
            continue
        try:
            print(f"\nAgente> {agent.respond(text)}")
        except Exception as exc:
            print(f"Erro: {exc}", file=sys.stderr)
    

def main() -> int:
    parser = argparse.ArgumentParser(description="Brazilian Portuguese Master Agent")
    parser.add_argument("--provider", choices=["openai", "anthropic", "gemini"])
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--next", dest="next_action", action="store_true")
    args = parser.parse_args()

    try:
        agent = make_agent(args.provider)
    except Exception as exc:
        print(f"Startup error: {exc}", file=sys.stderr)
        return 2

    if args.status:
        print_json(agent.status())
        return 0
    if args.next_action:
        print_json(agent.next_action())
        return 0
    return repl(agent)


if __name__ == "__main__":
    raise SystemExit(main())
