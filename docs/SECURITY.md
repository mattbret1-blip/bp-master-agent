# Security notes

This starter project is intentionally small and local-first. It is not yet an authenticated multi-tenant SaaS service.

Do not commit `.env`, API keys, learner exports, or local database files.

Secret scanning runs in two places: the `gitleaks` pre-commit hook
(`.pre-commit-config.yaml`; run `pre-commit install` after cloning) and the
`security` job in `.github/workflows/ci.yml`, which scans every push and pull
request. If gitleaks flags a finding, rotate the exposed credential — do not
just allowlist it.

Before public deployment, add authentication, authorization, per-user records, rate limiting, request-size limits, secret management, audit logging, backup/restore, and an explicit deletion policy.
