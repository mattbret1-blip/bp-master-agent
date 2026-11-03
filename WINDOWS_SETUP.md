# Run it on Windows (full features)

This is the recommended way to test the tutor live: everything runs on your
own machine, learner state stays in a local SQLite file, and your provider
API key never leaves your computer.

## 1. Prerequisites

- Windows 10/11
- Python 3.11–3.13 (3.12 recommended) from python.org — during install,
  check **"Add python.exe to PATH"**
- Git for Windows
- A provider API key + model for **one** provider:
  - OpenAI: `OPENAI_API_KEY` + `OPENAI_MODEL`
  - Anthropic: `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL`
  - Gemini: `GEMINI_API_KEY` + `GEMINI_MODEL`
  - Use a model name your key actually has access to (see your provider's
    dashboard). Voice in/out currently uses OpenAI only (see below).

## 2. Get the code

```bat
git clone https://github.com/mattbret1-blip/bp-master-agent.git
cd bp-master-agent
```

## 3. Set up (one time)

Double-click `setup.bat`, or run these steps yourself in Command Prompt
from the project folder:

```bat
py -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Then open `.env` in a text editor and set:

```ini
AI_PROVIDER=openai
OPENAI_API_KEY=your-key-here
OPENAI_MODEL=your-model-here
```

(Replace `openai` with `anthropic` or `gemini` and use that provider's two
variables instead, if you prefer.) Your key stays in this local `.env`
file — it is git-ignored and is never committed.

## 4. Run it

Double-click `run.bat`, or:

```bat
.venv\Scripts\activate.bat
python -m uvicorn web.app:create_app --factory --host 127.0.0.1 --port 8000
```

Then open **http://127.0.0.1:8000** in your browser. The chat page opens
with the diagnostic: it asks your goal, context, instruction language,
and whether you use voice or text. Your answers seed your learner state.

Check readiness any time at **http://127.0.0.1:8000/ready** — if it
reports missing configuration, your key/model is not set in `.env`.

### CLI instead of the web UI

```bat
.venv\Scripts\activate.bat
python main.py
```

Commands inside the CLI: `/status` `/next` `/export` `/reset` `/quit`,
plus `/say <text>` (synthesize speech to a `.wav` file) and
`/transcribe <audio-file>` (transcribe an audio file).

## 5. Optional features (set in `.env`)

```ini
MULTI_AGENT=true
CROSS_VALIDATE=true
VOICE_PROVIDER=openai
```

- `MULTI_AGENT=true` — each specialist (tutor, linguist, conversation,
  culture, assessor) makes its own call and the manager synthesizes them.
  Default off (single-call path).
- `CROSS_VALIDATE=true` — runs the cross-validate + revalidate loop after
  synthesis (requires `MULTI_AGENT=true`). Invalid claims are dropped and
  logged, never applied. Default off.
- `VOICE_PROVIDER=openai` — enables `/say`, `/transcribe`, and the web
  `/voice/*` endpoints. Requires `OPENAI_API_KEY`; the STT/TTS models and
  voice are configurable via `OPENAI_STT_MODEL`, `OPENAI_TTS_MODEL`,
  `OPENAI_TTS_VOICE` (defaults: `gpt-4o-transcribe`, `gpt-4o-mini-tts`,
  `alloy`).

## 6. Your learner state

State lives in `data\learner.db` (created on first run). Back it up by
copying that file. Deleting it resets the learner to a fresh diagnostic.
To keep a backup separate from the live database, copy it somewhere else
— do not commit it (it is git-ignored).

## 7. Troubleshooting

- `'py' is not recognized` — reinstall Python with "Add python.exe to
  PATH" checked, then open a fresh Command Prompt.
- `Port 8000 is already in use` — stop the other process, or run uvicorn
  with `--port 8001` and open `http://127.0.0.1:8001` instead.
- `/ready` says configuration is missing — re-check `.env`: the provider
  name in `AI_PROVIDER` must match the key/model variables you filled in.
- A chat turn errors — the CLI prints the error; the web UI returns it
  in the response. Common cause: a key without access to the chosen
  model, or no network route to the provider.
- Live provider calls have not been tested by the developers in this
  environment (no keys here) — if a provider call fails, the error text
  from the provider is the first thing to check.
