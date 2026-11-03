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
agent/specialists.py     True multi-agent team (MULTI_AGENT=true): one
                         structured call per specialist + manager synthesis
agent/specialist_models.py  Pydantic output schemas for each specialist
adapters/                Provider-specific OpenAI / Anthropic / Gemini code
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
| `RESEARCH_ENABLED` | Enable the bundled local-knowledge research adapter |
| `LOCAL_KNOWLEDGE_PATH` | Local research source directory |
| `APP_HOST` / `APP_PORT` | Server binding |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenAI configuration |
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Anthropic configuration |
| `GEMINI_API_KEY` / `GEMINI_MODEL` | Gemini configuration |

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
