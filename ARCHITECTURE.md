# V3 Architecture Notes

## Separation of concerns

### Model
Generates routing and instructional/assessment decisions.

### Orchestrator
Coordinates routing, specialist prompts, quality gate, research hook, and state transitions.

### State layer
SQLite stores the current learner profile plus immutable-ish event history.

### Competency layer
A prerequisite graph represents instructional dependencies. Mastery is updated from evidence, not from prose assertions.

### Retention layer
Review items use a lightweight spaced-repetition schedule.

### Provider layer
OpenAI, Anthropic, and Gemini adapters implement one `generate_structured` contract.

### Modality layer
Voice is abstracted behind `AudioAdapter`; speech recognition and synthesis can be implemented independently of the LLM provider.

## Why the model does not directly write the learner record

LLMs are probabilistic. Durable learner state should be deterministic, inspectable, exportable, and auditable. The model may propose evidence and updates, but application code applies rules.

## Multi-agent pattern

The manager routes bounded work to specialists. This preserves one user-facing owner while allowing expert behaviors for linguistics, conversation, culture, and assessment.

## Production path

Add:
- authenticated users and per-user databases
- encrypted secrets
- real web search or MCP tools
- speech-to-text / text-to-speech provider adapters
- telemetry and evaluation harness
- background scheduling for review reminders
- model selection policy (fast model for routing/review, stronger model for assessment or difficult linguistic analysis)
