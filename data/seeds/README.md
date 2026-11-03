# Seed data

Versioned starter content, committed to the repo:

- `curriculum.json` — the competency graph every new learner starts from.

Runtime state is **never** committed:

- `data/learner.db` (SQLite learner state) and any `data/*.db*` files are
  gitignored. Each deployment starts from these seeds and builds its own
  runtime database via `migrations/`.

To reset a learner back to seed state, delete the runtime database and let
the app recreate it — or use `python scripts/migrate.py down --to 0`
followed by `up`.
