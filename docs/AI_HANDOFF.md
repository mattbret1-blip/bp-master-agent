# AI coding-agent handoff

This repository is intentionally structured so OpenAI/ChatGPT, Claude, and Gemini coding agents can inspect and modify the same source of truth.

## Canonical rules

1. Read `AGENT.md`, `ARCHITECTURE.md`, and this file before changing architecture.
2. Inspect the complete repository before proposing a redesign.
3. Preserve the provider-neutral core and isolate provider-specific behavior under `adapters/`.
4. Keep durable learner state in application code; the model only proposes state changes/evidence.
5. Preserve the CEFR evidence gate, competency prerequisites, adaptive next-best-action, spaced repetition, and specialist routing.
6. Add tests for behavior changes.
7. Never claim a provider or deployment target was live-tested unless credentials and the target runtime were actually used.
8. Prefer the existing schemas and Pydantic models over ad-hoc JSON parsing.

## Claude implementation instruction

Read the entire repository, implement requested changes directly, run the tests, inspect failures, patch them, and report exact files changed plus test results. Do not reduce this system to a single prompt or replace durable application state with model memory.

## Gemini implementation instruction

Treat the repository as an executable software project, not a prompt-writing exercise. Inspect all modules and dependencies, preserve the adapter boundary, implement the requested feature, run tests/compile checks, and document any unverified live-provider behavior.

## OpenAI/ChatGPT coding instruction

Use the repository files as the source of truth. Make concrete edits, validate them, and keep provider-specific code inside adapters. Treat `AGENT.md` as the educational constitution and `ARCHITECTURE.md` as the systems boundary.
