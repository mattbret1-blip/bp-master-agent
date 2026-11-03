# Deployment

This project is designed to run as a stateless API process plus a persistent learner-state volume. The current reference deployment is Docker Compose; move the same container to a managed container platform when external users are added.

## 1. Local Docker deployment

```bash
cp .env.example .env
# edit .env and set the active provider key + model

docker compose up --build
```

Open `http://127.0.0.1:8000`.

Learner state is stored in the named Docker volume `bp_agent_data`.

## 2. Production checklist

Before exposing the API to the Internet:

- Put the app behind HTTPS and a reverse proxy/load balancer.
- Store API keys in the deployment platform's secret manager.
- Restrict `CORS_ORIGINS` to the real frontend origin(s).
- Replace the single shared SQLite state with authenticated, per-user storage.
- Add request authentication and authorization.
- Add rate limits and abuse controls.
- Configure centralized logs and error tracking.
- Back up learner-state storage.
- Decide data-retention and deletion policies before collecting production learner data.

## 3. Cloud Run / ECS / App Service / Fly.io pattern

The repository does not depend on a specific hosting vendor. Deploy the `Dockerfile`, expose TCP port `8000`, inject `.env` values as secrets/environment variables, and mount or attach persistent storage for `STATE_PATH`.

For multi-user production, keep the API process itself stateless and move learner state into a managed database. The model provider remains a replaceable adapter.

## 4. Database migrations

On startup, `agent.db.Database` applies SQL files in `migrations/` and records completed versions in `schema_migrations`. Existing v3 databases are compatible with migration `0001_initial.sql` because the initial tables use `CREATE TABLE IF NOT EXISTS`.

To add a migration:

1. Create the next numbered SQL file, e.g. `0002_add_user_id.sql`.
2. Make the migration idempotent when practical.
3. Add or update tests covering the new schema behavior.
4. Run the full test suite before deployment.

## 5. Health endpoints

`GET /health` is a lightweight process check. It should not require a paid model call and is suitable for container health probes.

`GET /ready` checks whether the application can initialize its configured provider and state path. A successful readiness check may still not prove that a remote provider will accept a live model request; perform a credentialed smoke test separately.
