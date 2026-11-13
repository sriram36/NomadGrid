"""Effective availability = catalog numbers minus what our own confirmed reservations used (S2)."""
from datetime import date
from typing import Dict, Optional, Tuple


class Inventory:
    def __init__(self, cat, used_seats: Optional[Dict[str, int]] = None,
                 used_rooms: Optional[Dict[Tuple[str, date], int]] = None):
        self.cat = cat
        self.used_seats = used_seats or {}
        self.used_rooms = used_rooms or {}

    def seats_left(self, flight: dict) -> int:
        return max(0, flight["seats_left"] - self.used_seats.get(flight["flight_id"], 0))

    def rooms_left(self, room_id: str, day: date) -> int:
        return max(0, self.cat.rooms_left(room_id, day) - self.used_rooms.get((room_id, day), 0))
