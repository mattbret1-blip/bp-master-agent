# Coding-agent instructions

This repository contains an agentic Brazilian Portuguese learning system. Treat the source tree as an executable software project.

## Before editing

Read, in order:

1. `AGENT.md` — educational constitution and behavior requirements
2. `ARCHITECTURE.md` — system boundaries
3. `README.md` — runtime and repository map
4. `docs/AI_HANDOFF.md` — cross-provider coding-agent rules

Then inspect the relevant implementation and tests before changing it.

## Non-negotiable architecture

- Keep provider-specific API behavior inside `adapters/`.
- Keep orchestration/provider-neutral in `agent/`.
- Durable learner state is owned by application code, not model memory.
- Preserve structured decisions and Pydantic validation.
- Preserve evidence-gated CEFR updates and the competency prerequisite graph.
- Do not silently weaken educational or evidence discipline to make a model response easier to generate.

## Implementation standard

Implement the change rather than merely describing it. Add or update tests. Run compile checks and the full test suite. For provider changes, perform live smoke tests only when credentials and network access are actually available.

Never state that a live vendor API, cloud deployment, Docker build, or external integration was tested unless it actually was.
