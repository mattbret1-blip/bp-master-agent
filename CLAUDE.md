# Claude instructions

Use the repository as the canonical source of truth. Read `AGENTS.md`, `AGENT.md`, `ARCHITECTURE.md`, and `docs/AI_HANDOFF.md` first.

Default to action: inspect the codebase, implement requested changes, run tests, patch failures, and report the exact result. Do not reduce the system to a single prompt. Preserve the adapter boundary and application-owned learner state.

When changing the learning behavior, keep the Goal → Obstacle → Context framework, domain-specific CEFR evidence, competency prerequisites, recurring-error tracking, spaced repetition, and specialist roles intact unless a deliberate architectural change is explicitly requested.
