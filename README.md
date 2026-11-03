# Brazilian Portuguese Master Agent v3.1

A provider-neutral, stateful, agentic Brazilian Portuguese learning platform designed to run with OpenAI, Anthropic Claude, or Google Gemini.

The key design principle is simple: **the model proposes; the application owns durable learner state.** This keeps progress inspectable, exportable, testable, and independent of a single model vendor.

## What is included

- Manager/orchestrator plus specialist roles for tutoring, linguistics, conversation, culture, and assessment
- Durable SQLite learner memory, event log, and run telemetry
- Competency/prerequisite graph
- Evidence-gated CEFR tracking by domain
- Adaptive next-best-action selection
- Spaced repetition and review queue
- Recurring error and vocabulary tracking
- Optional quality gate
- Pluggable research and voice interfaces
- FastAPI API + browser UI
- Local CLI
- Provider switching without resetting learner state
- SQL migrations
- Docker + Docker Compose
- GitHub Actions CI across Python 3.11–3.13
- AI-agent handoff instructions for Claude, Gemini, and OpenAI/ChatGPT

## Repository map

```text
AGENT.md                 Educational constitution / master specification
ARCHITECTURE.md          System boundaries and design rationale
main.py                  Local interactive CLI
agent/                   Core orchestration, state, curriculum, scheduling
agent/audio.py           Voice-adapter factory (VOICE_PROVIDER) + MIME helper
agent/specialists.py     True multi-agent team (MULTI_AGENT=true): one
                         structured call per specialist + manager synthesis
agent/validation.py      Cross-validation loop (CROSS_VALIDATE=true):
                         deterministic checks + LLM validation, one bounded
                         re-synthesis round, validated-subset application
agent/specialist_models.py  Pydantic output schemas for each specialist
agent/voice.py           AudioAdapter protocol (transcribe / synthesize)
adapters/                Provider-specific OpenAI / Anthropic / Gemini code
adapters/openai_voice.py  OpenAI speech-to-text + text-to-speech adapter
schemas/                 Structured-output JSON schemas
skills/                  Specialist behavior modules
data/                    Seed curriculum (data/seeds, committed) and local
                       knowledge; runtime databases (data/*.db) are gitignored
migrations/              SQLite schema migrations (each with a .down.sql rollback)
scripts/migrate.py       up / down / status helper for the learner database
tests/                   Provider-neutral automated tests (unit / integration /
                       conformance tiers)
web/                     FastAPI app and browser UI
tests/                   Provider-neutral automated tests
docs/                    Deployment, operations, provider, security, AI handoff
Dockerfile               Production-oriented container image
docker-compose.yml       Local persistent container deployment
.github/workflows/ci.yml GitHub Actions validation (tests + secret scan)
.pre-commit-config.yaml  Local pre-commit hooks (whitespace, YAML, gitleaks)
```

## Local development

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt   # or requirements-lock.txt for pinned, reproducible installs
cp .env.example .env
pip install pre-commit && pre-commit install   # enable the gitleaks secret-scan hook
```

Set the active provider credentials and model in `.env`.

Run tests:

```bash
pytest
```

Run the CLI:

```bash
python main.py
```

Or:

```bash
bp-agent
```

Run the browser app:

```bash
uvicorn web.app:create_app --factory --host 0.0.0.0 --port 8000 --reload
```

Open `http://127.0.0.1:8000`.

## Docker

```bash
cp .env.example .env
# edit .env

docker compose up --build
```

The learner database lives in the persistent `bp_agent_data` volume.

## Environment variables

| Variable | Purpose |
|---|---|
| `AI_PROVIDER` | `openai`, `anthropic`, or `gemini` |
| `STATE_PATH` | SQLite learner state path |
| `MAX_HISTORY_MESSAGES` | Maximum conversational history sent to the model |
| `QUALITY_GATE` | Enable the independent quality pass |
| `MULTI_AGENT` | `true` routes each turn through `SpecialistTeam` (one structured call per routed specialist + manager synthesis); default `false` keeps the original single-call path |
| `CROSS_VALIDATE` | `true` enables the cross-validation loop, but only on the multi-agent path (`MULTI_AGENT=true`); default `false` leaves behavior unchanged |
| `RESEARCH_ENABLED` | Enable the bundled local-knowledge research adapter |
| `LOCAL_KNOWLEDGE_PATH` | Local research source directory |
| `APP_HOST` / `APP_PORT` | Server binding |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI configuration |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Anthropic configuration |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini configuration |
| `VOICE_PROVIDER` | Voice adapter: `openai` (the only one implemented) |
| `OPENAI_STT_MODEL` | Speech-to-text model (default `gpt-4o-transcribe`) |
| `OPENAI_TTS_MODEL` | Text-to-speech model (default `gpt-4o-mini-tts`) |
| `OPENAI_TTS_VOICE` | TTS voice (default `alloy`) |

## Voice in/out

File-based speech, no live playback: the CLI writes synthesized audio to a
`.wav` file, and transcription reads an audio file you point it at.

```bash
# Inside the CLI (python main.py):
/say Olá, tudo bem?          # writes say-YYYYMMDD-HHMMSS.wav in the working directory
/transcribe recording.wav    # prints the transcript
```

Web endpoints (multipart upload for transcription, raw audio bytes back for
synthesis):

```bash
curl -F "file=@recording.wav" http://127.0.0.1:8000/voice/transcribe
curl -X POST -H "Content-Type: application/json" \
  -d '{"text": "Olá, tudo bem?"}' \
  http://127.0.0.1:8000/voice/synthesize -o speech.wav
```

When voice is not configured (no `OPENAI_API_KEY`), the CLI prints a clear
"Voz indisponível" error and the web endpoints return 503 — the app itself
keeps running.

**Live-voice status: NOT tested.** No provider API keys exist in this
environment, so the OpenAI voice adapter has never made a live call. All
automated voice tests run offline against a fake adapter; live STT/TTS
verification still awaits real credentials.

## Cross-validation loop

With `MULTI_AGENT=true` and `CROSS_VALIDATE=true`, every turn runs a
synthesize → cross-validate → revalidate loop between the manager's
synthesis and state application:

1. **Deterministic checks (app code, no model):** evidence must reference
   a known competency; CEFR proposals must name a real domain and level;
   one turn must not claim mastery of a concept it also flags as a
   recurring error; response prose must not claim a CEFR level or mastery
   the decision's own evidence does not support.
2. **LLM validation call:** one structured call cross-checking the
   specialist contributions against each other and against the learner's
   evidence record, returning a verdict (`pass` / `fixable` / `reject`)
   and issues with severities.
3. **One bounded re-synthesis round:** if the verdict is `fixable` and
   issues remain, the manager repairs the decision with the issues in
   hand (specialists are not re-run). Maximum 2 synthesis rounds total,
   then the loop stops whatever the state.
4. **Validated subset only:** invalid evidence items and contradictory
   state updates are dropped — never applied — and logged as a
   `validation` database event naming exactly what was dropped and why.
   A `reject` verdict drops all recordable claims while keeping the
   learner-facing response. A compact summary (rounds used, verdict,
   issues found, dropped items) is included in the agent's status output
   (`GET /api/status`, CLI `/status`) so comprehension evaluation stays
   inspectable.
5. **Fallback:** if the validation call itself fails, the turn proceeds
   with the pre-validation decision and a `validation_fallback` event is
   logged. A validation outage never breaks a tutoring turn.

Validated evidence still flows through the existing evidence and CEFR
gates in `agent/core.py` — validation can only make recording stricter,
never looser. With either flag off, behavior is exactly the previous
behavior.

**Live-provider status: NOT tested.** No provider API keys exist in this
environment, so the validation LLM call has never run against a live
provider. All automated cross-validation tests run offline against a
fake adapter.

## API

`GET /health` — process health check

`GET /ready` — provider/configuration readiness check

`GET /api/status` — durable learner state

`GET /api/next` — next-best action

`GET /api/review` — current review candidates

`POST /api/chat` — send a learner message

`POST /api/provider` — switch provider while preserving state

`POST /api/reset` — reset local learner state

`GET /api/export` — export state + event log

`POST /voice/transcribe` — multipart audio upload → JSON transcript

`POST /voice/synthesize` — JSON `{"text", "voice"?}` → audio/wav bytes

## Architecture

```text
Learner
  ↓
FastAPI / CLI
  ↓
Master Orchestrator
  ├─ Router
  ├─ Tutor
  ├─ Linguist
  ├─ Conversation
  ├─ Culture
  └─ Assessor
  ↓
Structured Decision
  ↓
Quality Gate (optional)
  ↓
Application-Owned State Transition
  ├─ CEFR evidence
  ├─ Competency graph
  ├─ Error/vocabulary memory
  └─ Review scheduler
  ↓
Next Best Action
```

## CEFR/evidence discipline

The agent does not treat a single model assertion as proof of proficiency. Evidence is tracked by domain and by stage: Recognition → Recall → Controlled Production → Spontaneous Production → Automaticity. Durable CEFR movement is conservative and evidence-gated.

## Working with Claude, Gemini, or OpenAI/ChatGPT

Use the repository itself as the canonical source of truth rather than copying only `AGENT.md`. The complete source tree is designed for AI coding agents to inspect, modify, test, and deploy.

Start with `docs/AI_HANDOFF.md`, `AGENT.md`, `ARCHITECTURE.md`, and `README.md`.

## Deployment

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md), [`docs/OPERATIONS.md`](docs/OPERATIONS.md), and [`docs/SECURITY.md`](docs/SECURITY.md).

The current reference deployment is a Docker container with persistent learner-state storage. For multi-user production, replace the process-local single learner state with authenticated per-user persistence.
