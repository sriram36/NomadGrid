"""SQLite persistence: packages and reservations. State survives refresh and backend restarts."""
import json
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS packages (
    id           TEXT PRIMARY KEY,
    status       TEXT NOT NULL,
    package_json TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reservations (
    number        TEXT PRIMARY KEY,
    package_id    TEXT NOT NULL UNIQUE,
    snapshot_json TEXT NOT NULL,
    created_at    TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_reservation_number() -> str:
    """Random 10-digit number, first digit 1-9, returned as a string."""
    return str(secrets.randbelow(9 * 10 ** 9) + 10 ** 9)


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as c:
            c.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.path), timeout=15, isolation_level=None)   # manual transactions
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA journal_mode=WAL")
        return c

    # ------------------------------------------------------------------ packages
    def save_package(self, pkg: dict) -> None:
        with closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            c.execute(
                "INSERT INTO packages (id, status, package_json, created_at, updated_at) VALUES (?,?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET status=excluded.status, package_json=excluded.package_json, "
                "updated_at=excluded.updated_at",
                (pkg["package_id"], pkg["status"], json.dumps(pkg), _now(), _now()))
            c.execute("COMMIT")

    def get_package(self, package_id: str) -> Optional[dict]:
        with closing(self._connect()) as c:
            row = c.execute("SELECT package_json FROM packages WHERE id=?", (package_id,)).fetchone()
        return json.loads(row["package_json"]) if row else None

    # ------------------------------------------------------------------ reservations
    def get_reservation(self, number: str) -> Optional[dict]:
        with closing(self._connect()) as c:
            row = c.execute("SELECT snapshot_json FROM reservations WHERE number=?", (number,)).fetchone()
        return json.loads(row["snapshot_json"]) if row else None

    def reservation_for_package(self, package_id: str) -> Optional[Tuple[str, dict]]:
        with closing(self._connect()) as c:
            row = c.execute("SELECT number, snapshot_json FROM reservations WHERE package_id=?",
                            (package_id,)).fetchone()
        return (row["number"], json.loads(row["snapshot_json"])) if row else None

    def confirm(self, package_id: str, make_booked: Callable[[dict, str, str], dict]) -> Optional[Tuple[str, dict]]:
        """Create (or return the existing) reservation for a package, atomically.

        `make_booked(package, number, confirmed_at)` must return the BOOKED package dict.
        Returns (number, booked_package) or None if the package does not exist.
        """
        with closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                existing = c.execute("SELECT number, snapshot_json FROM reservations WHERE package_id=?",
                                     (package_id,)).fetchone()
                if existing:
                    c.execute("COMMIT")
                    return existing["number"], json.loads(existing["snapshot_json"])
                row = c.execute("SELECT package_json FROM packages WHERE id=?", (package_id,)).fetchone()
                if row is None:
                    c.execute("COMMIT")
                    return None
                pkg = json.loads(row["package_json"])
                for _ in range(50):
                    number = new_reservation_number()
                    if c.execute("SELECT 1 FROM reservations WHERE number=?", (number,)).fetchone():
                        continue
                    booked = make_booked(pkg, number, _now())
                    c.execute("INSERT INTO reservations (number, package_id, snapshot_json, created_at) "
                              "VALUES (?,?,?,?)", (number, package_id, json.dumps(booked), _now()))
                    c.execute("UPDATE packages SET status=?, package_json=?, updated_at=? WHERE id=?",
                              ("BOOKED", json.dumps(booked), _now(), package_id))
                    c.execute("COMMIT")
                    return number, booked
                raise RuntimeError("could not allocate a unique reservation number")
            except Exception:
                c.execute("ROLLBACK")
                raise
