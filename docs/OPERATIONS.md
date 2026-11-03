# Operations

## Startup

```bash
uvicorn web.app:create_app --factory --host 0.0.0.0 --port 8000
```

## CLI

```bash
bp-agent
bp-agent --provider gemini
bp-agent --status
bp-agent --next
```

## State export

`GET /api/export` returns the current learner state and event log. Treat exported records as learner data and protect them appropriately.

## Reset

`POST /api/reset` clears the local learner state and event/run history for the configured database.

## Provider status

`GET /api/status` reports the current agent state. It does not expose API secrets.
