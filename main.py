from __future__ import annotations

import argparse
import json
import sys

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


def repl(agent: BrazilianPortugueseAgent) -> int:
    opening = agent.opening_diagnostic()
    if opening:
        print(opening)
    print("\nCommands: /status /next /export /reset /quit")
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
