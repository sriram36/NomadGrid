"""SQLite persistence: packages, reservations, our own seat/room usage (S2) and undo history.

State survives refresh and backend restarts.
"""
import json
import secrets
import sqlite3
from contextlib import closing
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

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
CREATE TABLE IF NOT EXISTS inventory_used (
    kind TEXT NOT NULL,              -- 'SEAT' (key = flight_id) or 'ROOM' (key = room_id, day = the night)
    key  TEXT NOT NULL,
    day  TEXT NOT NULL DEFAULT '',
    qty  INTEGER NOT NULL,
    PRIMARY KEY (kind, key, day)
);
CREATE TABLE IF NOT EXISTS package_history (
    seq          INTEGER PRIMARY KEY AUTOINCREMENT,
    package_id   TEXT NOT NULL,
    package_json TEXT NOT NULL,
    created_at   TEXT NOT NULL
);
"""

HISTORY_LIMIT = 20


class InventoryConflict(Exception):
    """A booking needs seats or rooms that our own confirmed reservations have already used up."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_reservation_number() -> str:
    """Random 10-digit number, first digit 1-9, returned as a string."""
    return str(secrets.randbelow(9 * 10 ** 9) + 10 ** 9)


def package_needs(pkg: dict) -> Tuple[Dict[str, int], Dict[Tuple[str, str], int]]:
    """Seats per flight and rooms per (room, night) that a package books."""
    seats: Dict[str, int] = {}
    rooms: Dict[Tuple[str, str], int] = {}
    for i in pkg["items"]:
        if i["type"] == "flight":
            seats[i["catalog_id"]] = seats.get(i["catalog_id"], 0) + i["quantity"]
        elif i["type"] == "hotel":
            ci, co = date.fromisoformat(i["start"]), date.fromisoformat(i["end"])
            for n in range((co - ci).days):
                key = (i["room_id"], (ci + timedelta(days=n)).isoformat())
                rooms[key] = rooms.get(key, 0) + i["quantity"]
    return seats, rooms


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
    def save_package(self, pkg: dict, keep_history: bool = False) -> None:
        """Insert or update a package. With keep_history the previous version is kept for Undo."""
        with closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            if keep_history:
                old = c.execute("SELECT package_json FROM packages WHERE id=?", (pkg["package_id"],)).fetchone()
                if old:
                    c.execute("INSERT INTO package_history (package_id, package_json, created_at) VALUES (?,?,?)",
                              (pkg["package_id"], old["package_json"], _now()))
                    c.execute("DELETE FROM package_history WHERE package_id=? AND seq NOT IN "
                              "(SELECT seq FROM package_history WHERE package_id=? ORDER BY seq DESC LIMIT ?)",
                              (pkg["package_id"], pkg["package_id"], HISTORY_LIMIT))
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

    def undo(self, package_id: str) -> Optional[dict]:
        """Restore the previous version of a package; None when there is nothing to undo."""
        with closing(self._connect()) as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT seq, package_json FROM package_history WHERE package_id=? "
                            "ORDER BY seq DESC LIMIT 1", (package_id,)).fetchone()
            if row is None:
                c.execute("COMMIT")
                return None
            restored = json.loads(row["package_json"])
            c.execute("DELETE FROM package_history WHERE seq=?", (row["seq"],))
            c.execute("UPDATE packages SET status=?, package_json=?, updated_at=? WHERE id=?",
                      (restored["status"], row["package_json"], _now(), package_id))
            c.execute("COMMIT")
        return restored

    def history_count(self, package_id: str) -> int:
        with closing(self._connect()) as c:
            return c.execute("SELECT COUNT(*) AS n FROM package_history WHERE package_id=?", (package_id,)).fetchone()["n"]

    # ------------------------------------------------------------------ our own inventory (S2)
    def used_maps(self) -> Tuple[Dict[str, int], Dict[Tuple[str, date], int]]:
        """Seats used per flight and rooms used per (room, night) by confirmed reservations."""
        seats: Dict[str, int] = {}
        rooms: Dict[Tuple[str, date], int] = {}
        with closing(self._connect()) as c:
            for r in c.execute("SELECT kind, key, day, qty FROM inventory_used"):
                if r["kind"] == "SEAT":
                    seats[r["key"]] = r["qty"]
                else:
                    rooms[(r["key"], date.fromisoformat(r["day"]))] = r["qty"]
        return seats, rooms

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

    def confirm(self, package_id: str, make_booked: Callable[[dict, str, str], dict],
                cat=None) -> Optional[Tuple[str, dict]]:
        """Create (or return the existing) reservation for a package, atomically.

        `make_booked(package, number, confirmed_at)` returns the BOOKED package dict. When `cat` (the catalog)
        is given, the booking also uses up seats and rooms in our own store (S2): if the last seats or rooms
        are already gone, InventoryConflict is raised and nothing is booked.
        Returns (number, booked_package), or None if the package does not exist.
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
                if cat is not None:
                    self._use_up(c, pkg, cat)
                for _ in range(50):
                    number = new_reservation_number()
                    if c.execute("SELECT 1 FROM reservations WHERE number=?", (number,)).fetchone():
                        continue
                    booked = make_booked(pkg, number, _now())
                    c.execute("INSERT INTO reservations (number, package_id, snapshot_json, created_at) "
                              "VALUES (?,?,?,?)", (number, package_id, json.dumps(booked), _now()))
                    c.execute("UPDATE packages SET status=?, package_json=?, updated_at=? WHERE id=?",
                              ("BOOKED", json.dumps(booked), _now(), package_id))
                    c.execute("DELETE FROM package_history WHERE package_id=?", (package_id,))
                    c.execute("COMMIT")
                    return number, booked
                raise RuntimeError("could not allocate a unique reservation number")
            except Exception:
                c.execute("ROLLBACK")
                raise

    @staticmethod
    def _use_up(c: sqlite3.Connection, pkg: dict, cat) -> None:
        """Check the seats/rooms this package needs against catalog minus our usage, then record the usage."""
        seats, rooms = package_needs(pkg)
        used = {(r["kind"], r["key"], r["day"]): r["qty"]
                for r in c.execute("SELECT kind, key, day, qty FROM inventory_used")}
        for fid, need in seats.items():
            f = cat.flights[fid]
            left = f["seats_left"] - used.get(("SEAT", fid, ""), 0)
            if left < need:
                raise InventoryConflict(
                    f"Flight {f['flight_number']} ({fid}) has only {max(left, 0)} seat(s) left, and this holiday "
                    f"needs {need}. Another booking took them.")
        for (room_id, day), need in rooms.items():
            left = cat.rooms_left(room_id, date.fromisoformat(day)) - used.get(("ROOM", room_id, day), 0)
            if left < need:
                hotel = cat.hotels[cat.rooms[room_id]["hotel_id"]]
                raise InventoryConflict(
                    f"{hotel['name']} has only {max(left, 0)} room(s) left on {date.fromisoformat(day):%d %b}, and this "
                    f"holiday needs {need}. Another booking took them.")
        for fid, need in seats.items():
            c.execute("INSERT INTO inventory_used (kind, key, day, qty) VALUES ('SEAT', ?, '', ?) "
                      "ON CONFLICT(kind, key, day) DO UPDATE SET qty = qty + excluded.qty", (fid, need))
        for (room_id, day), need in rooms.items():
            c.execute("INSERT INTO inventory_used (kind, key, day, qty) VALUES ('ROOM', ?, ?, ?) "
                      "ON CONFLICT(kind, key, day) DO UPDATE SET qty = qty + excluded.qty", (room_id, day, need))
