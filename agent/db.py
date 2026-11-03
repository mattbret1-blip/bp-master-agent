from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import AgentState


class Database:
    def __init__(self, path="data/learner.db", migrations_dir=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.migrations_dir = Path(migrations_dir) if migrations_dir else Path(__file__).resolve().parents[1] / "migrations"
        self._migrate()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def applied_versions(self) -> set[int]:
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)"
        )
        self.conn.commit()
        return {
            row["version"]
            for row in self.conn.execute("SELECT version FROM schema_migrations")
        }

    def _migrate(self):
        applied = self.applied_versions()
        if not self.migrations_dir.exists():
            return
        # NOTE: *.down.sql files are rollback scripts — never apply them going up.
        migrations = sorted(
            p
            for p in self.migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.sql")
            if not p.name.endswith(".down.sql")
        )
        for path in migrations:
            try:
                version = int(path.name.split("_", 1)[0])
            except ValueError:
                continue
            if version in applied:
                continue
            sql = path.read_text(encoding="utf-8")
            with self.conn:
                self.conn.executescript(sql)
                self.conn.execute(
                    "INSERT INTO schema_migrations(version) VALUES(?)", (version,)
                )

    def upgrade(self) -> list[int]:
        """Apply pending migrations. Returns the versions that were applied."""
        before = self.applied_versions()
        self._migrate()
        return sorted(self.applied_versions() - before)

    def downgrade(self, target_version: int = 0) -> list[int]:
        """Roll back applied migrations down to (but not including)
        target_version. Refuses to roll back a version that has no down
        script rather than leaving the schema half-reverted."""
        applied = sorted(self.applied_versions(), reverse=True)
        if not self.migrations_dir.exists():
            return []
        down_files: dict[int, Path] = {}
        for path in self.migrations_dir.glob("[0-9][0-9][0-9][0-9]_*.down.sql"):
            try:
                down_files[int(path.name.split("_", 1)[0])] = path
            except ValueError:
                continue
        rolled_back: list[int] = []
        for version in applied:
            if version <= target_version:
                break
            path = down_files.get(version)
            if path is None:
                raise RuntimeError(
                    f"No down migration for version {version}; "
                    "refusing to roll back further"
                )
            with self.conn:
                self.conn.executescript(path.read_text(encoding="utf-8"))
                self.conn.execute(
                    "DELETE FROM schema_migrations WHERE version = ?", (version,)
                )
            rolled_back.append(version)
        return rolled_back

    def load_state(self):
        row = self.conn.execute(
            "SELECT value FROM kv WHERE key='state'"
        ).fetchone()
        return AgentState.model_validate_json(row["value"]) if row else AgentState()

    def save_state(self, state):
        self.conn.execute(
            "INSERT INTO kv(key,value) VALUES('state',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (state.model_dump_json(),),
        )
        self.conn.commit()

    def event(self, kind, payload):
        self.conn.execute(
            "INSERT INTO events(created_at,kind,payload) VALUES(?,?,?)",
            (self._now(), kind, json.dumps(payload, ensure_ascii=False)),
        )
        self.conn.commit()

    def run_log(self, provider, mode, latency_ms, input_chars, output_chars, route, decision):
        self.conn.execute(
            """INSERT INTO runs(
                created_at,provider,mode,latency_ms,input_chars,
                output_chars,route_json,decision_json
            ) VALUES(?,?,?,?,?,?,?,?)""",
            (
                self._now(), provider, mode, latency_ms,
                input_chars, output_chars,
                json.dumps(route, ensure_ascii=False),
                json.dumps(decision, ensure_ascii=False),
            ),
        )
        self.conn.commit()

    def reset(self):
        self.conn.execute("DELETE FROM kv")
        self.conn.execute("DELETE FROM events")
        self.conn.execute("DELETE FROM runs")
        self.conn.commit()

    def export_json(self):
        state = self.load_state()
        events = [
            dict(r) for r in self.conn.execute(
                "SELECT id,created_at,kind,payload FROM events ORDER BY id"
            ).fetchall()
        ]
        return {"state": state.model_dump(), "events": events}

    def close(self):
        self.conn.close()
