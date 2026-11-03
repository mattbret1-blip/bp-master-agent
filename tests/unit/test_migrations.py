"""Migration reversibility: up then down must cleanly remove schema objects."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from agent.db import Database

EXPECTED_TABLES = {"kv", "events", "runs"}


def _tables(db):
    return {
        row["name"]
        for row in db.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def test_migrate_up_then_down_roundtrip(tmp_path):
    db = Database(str(tmp_path / "t.db"))
    assert EXPECTED_TABLES <= _tables(db)

    rolled_back = db.downgrade()
    assert rolled_back == [1]
    assert not (EXPECTED_TABLES & _tables(db))

    # And back up again — the down script must not poison future upgrades.
    assert db.upgrade() == [1]
    assert EXPECTED_TABLES <= _tables(db)


def test_downgrade_refuses_when_down_script_missing(tmp_path):
    import shutil

    seed = Database(str(tmp_path / "seed.db"))
    isolated = tmp_path / "migrations"
    shutil.copytree(seed.migrations_dir, isolated)
    (isolated / "0001_initial.down.sql").unlink()

    db = Database(str(tmp_path / "t.db"), migrations_dir=isolated)
    with pytest.raises(RuntimeError, match="No down migration"):
        db.downgrade()
    # Schema must be untouched after the refusal.
    assert EXPECTED_TABLES <= _tables(db)


def test_down_files_are_not_applied_as_up_migrations(tmp_path):
    """The up-migration glob must ignore *.down.sql files."""
    db = Database(str(tmp_path / "t.db"))
    versions = [r["version"] for r in db.conn.execute("SELECT version FROM schema_migrations")]
    assert versions == [1]
    assert EXPECTED_TABLES <= _tables(db)
