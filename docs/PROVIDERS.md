# Provider integration

The core application depends on one internal adapter contract: `generate_structured(system, messages, schema, schema_name)`.

Provider-specific code is intentionally isolated in:

- `adapters/openai_adapter.py`
- `adapters/anthropic_adapter.py`
- `adapters/gemini_adapter.py`

The architecture relies on structured model output rather than parsing free-form prose. OpenAI, Anthropic, and Google each provide a structured-output mechanism compatible with this adapter boundary. See the official provider documentation referenced at the end of this file.

## OpenAI

Set:

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=...
```

## Anthropic

Set:

```dotenv
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=...
```

## Gemini

Set:

```dotenv
AI_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=...
```

Google's current Gen AI Python SDK uses `from google import genai` and `client.models.generate_content(...)`, with JSON output controlled through `response_mime_type` and `response_schema`.

## Switching providers

The learner state does not belong to the model provider. The FastAPI endpoint `/api/provider` swaps the adapter in-process while preserving the SQLite learner record.

For a real multi-user deployment, provider switching should be scoped to an authenticated user/session rather than globally changing one process-wide agent.

## Live smoke tests

The repository's automated tests use a fake adapter so CI does not need API credentials. Live provider validation should be run separately with real credentials and a model selected for each provider.

## Official provider references

- OpenAI Responses API / Structured Outputs: https://platform.openai.com/docs/api-reference/responses
- Anthropic tool use: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
- Gemini Generate Content / structured JSON: https://ai.google.dev/api/generate-content
