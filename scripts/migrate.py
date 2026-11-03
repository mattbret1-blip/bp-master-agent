"""Database migration helper.

Usage:
    python scripts/migrate.py up            # apply pending migrations
    python scripts/migrate.py down          # roll back the last applied migration
    python scripts/migrate.py down --to 0   # roll back everything
    python scripts/migrate.py status        # show applied versions
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.config import Settings
from agent.db import Database


def main() -> int:
    parser = argparse.ArgumentParser(description="Learner database migrations")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("up", help="Apply pending migrations")
    down = sub.add_parser("down", help="Roll back applied migrations")
    down.add_argument("--to", type=int, default=0, help="Roll back to this version")
    sub.add_parser("status", help="Show applied migration versions")
    args = parser.parse_args()

    db = Database(Settings.from_env().state_path)
    if args.cmd == "up":
        applied = db.upgrade()
        print("Applied: {}".format(applied) if applied else "Already up to date.")
    elif args.cmd == "down":
        rolled_back = db.downgrade(target_version=args.to)
        print("Rolled back: {}".format(rolled_back) if rolled_back else "Nothing to roll back.")
    else:
        print("Applied versions: {}".format(sorted(db.applied_versions())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
