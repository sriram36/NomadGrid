"""Read-only catalog: loads data/catalog/*.json once and builds lookup indexes.

Nothing here ever writes to the data files.
"""
import hashlib
import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Dict, List, Optional


def data_fingerprint(data_dir) -> str:
    """SHA-256 over every .json file under data_dir (used to prove the data is untouched)."""
    h = hashlib.sha256()
    for p in sorted(Path(data_dir).rglob("*.json")):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


class Catalog:
    def __init__(self, data_dir):
        base = Path(data_dir) / "catalog"

        def load(name):
            path = base / name
            if not path.is_file():
                raise FileNotFoundError(
                    f"Catalog file not found: {path}. Set the DATA_DIR environment variable to the folder that "
                    f"contains catalog/destinations.json, flights.json, hotels.json ... (the provided data pack).")
            return json.loads(path.read_text(encoding="utf-8"))

        self.destinations = load("destinations.json")
        self.airports: Dict[str, dict] = {a["code"]: a for a in load("airports.json")}
        self.flights: Dict[str, dict] = {}
        for f in load("flights.json"):
            f["_dep"] = datetime.fromisoformat(f["departure_local"])
            f["_arr"] = datetime.fromisoformat(f["arrival_local"])
            self.flights[f["flight_id"]] = f
        self.hotels: Dict[str, dict] = {h["hotel_id"]: h for h in load("hotels.json")}
        self.rooms: Dict[str, dict] = {r["room_id"]: r for r in load("rooms.json")}
        self.availability = {
            (a["room_id"], date.fromisoformat(a["date"])): a["rooms_left"] for a in load("availability.json")
        }
        self.transfers: Dict[str, dict] = {t["transfer_id"]: t for t in load("transfers.json")}
        self.attractions: Dict[str, dict] = {a["attraction_id"]: a for a in load("attractions.json")}
        self._index()

    # ------------------------------------------------------------------ indexes
    def _index(self):
        self._arr_idx = defaultdict(list)   # (from, date) -> flights by arrival date
        self._ret_idx = defaultdict(list)   # (to, date)   -> flights by departure date
        for f in self.flights.values():
            self._arr_idx[(f["from"], f["_arr"].date())].append(f)
            self._ret_idx[(f["to"], f["_dep"].date())].append(f)
        self._hotels_by_city = defaultdict(list)
        for h in self.hotels.values():
            self._hotels_by_city[h["city"]].append(h)
        self._rooms_by_hotel = defaultdict(list)
        for r in self.rooms.values():
            self._rooms_by_hotel[r["hotel_id"]].append(r)
        self._attr_by_city = defaultdict(list)
        for a in self.attractions.values():
            self._attr_by_city[a["city"]].append(a)
        self._airport_transfers = defaultdict(list)
        for t in self.transfers.values():
            if t.get("airport"):
                self._airport_transfers[(t["airport"], t["city"])].append(t)
        self._serving = defaultdict(list)
        for a in self.airports.values():
            for c in a.get("serves_cities", []):
                self._serving[c].append(a["code"])
        self._countries = {c["name"]: c for c in self.destinations["countries"]}
        self._dep_cities = {d["city"]: d["airport"] for d in self.destinations["departure_cities"]}

    # ------------------------------------------------------------------ lookups
    def departure_cities(self) -> List[dict]:
        return list(self.destinations["departure_cities"])

    def departure_airport(self, city: str) -> Optional[str]:
        return self._dep_cities.get(city)

    def country(self, name: str) -> Optional[dict]:
        return self._countries.get(name)

    def country_code(self, name: str) -> Optional[str]:
        c = self._countries.get(name)
        return c["code"] if c else None

    def cities_of(self, country_name: str) -> List[str]:
        c = self._countries.get(country_name)
        return [x["name"] for x in c["cities"]] if c else []

    def links_of(self, country_name: str) -> set:
        c = self._countries.get(country_name)
        return {(l["from_city"], l["to_city"]) for l in c["links"]} if c else set()

    def country_of_airport(self, code: str) -> Optional[str]:
        a = self.airports.get(code)
        return a["country"] if a else None

    def airports_serving(self, city: str) -> List[str]:
        return sorted(self._serving.get(city, []))

    def arrivals(self, dep_airport: str, country_code: str, day: date) -> List[dict]:
        """Flights from dep_airport into the country that LAND on `day` (local date)."""
        out = [f for f in self._arr_idx.get((dep_airport, day), [])
               if self.country_of_airport(f["to"]) == country_code]
        return sorted(out, key=lambda f: f["flight_id"])

    def returns(self, dep_airport: str, country_code: str, day: date) -> List[dict]:
        """Flights from the country back to dep_airport that LEAVE on `day` (local date)."""
        out = [f for f in self._ret_idx.get((dep_airport, day), [])
               if self.country_of_airport(f["from"]) == country_code]
        return sorted(out, key=lambda f: f["flight_id"])

    def rooms_left(self, room_id: str, day: date) -> int:
        return self.availability.get((room_id, day), 0)

    def hotels_in(self, city: str) -> List[dict]:
        return list(self._hotels_by_city.get(city, []))

    def rooms_of(self, hotel_id: str) -> List[dict]:
        return list(self._rooms_by_hotel.get(hotel_id, []))

    def attractions_in(self, city: str) -> List[dict]:
        return list(self._attr_by_city.get(city, []))

    def airport_transfers(self, airport: str, city: str) -> List[dict]:
        return list(self._airport_transfers.get((airport, city), []))

    def link_transfers(self, country_name: str, from_city: str, to_city: str) -> List[dict]:
        c = self._countries.get(country_name)
        if not c:
            return []
        for l in c["links"]:
            if l["from_city"] == from_city and l["to_city"] == to_city:
                return [self.transfers[i] for i in l["transfer_ids"]]
        return []

    @property
    def rules(self) -> dict:
        return self.destinations["rules"]
