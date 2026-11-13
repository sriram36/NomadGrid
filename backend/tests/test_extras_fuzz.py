"""Seeded invariant fuzz for the extra features. Random inputs, strict properties."""
import random
import tempfile
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.export.package import to_trip_format
from app.validator.validate import validate_trip


def random_request(rnd, cat):
    nights = rnd.randint(3, 9)
    return {
        "departure_city": rnd.choice([d["city"] for d in cat.departure_cities()]),
        "country": rnd.choice([c["name"] for c in cat.destinations["countries"]]),
        "start_date": (date(2027, 4, 1) + timedelta(days=rnd.randint(0, 19 - nights))).isoformat(),
        "nights": nights, "adults": rnd.choice([1, 2, 2, 3]),
        "child_ages": rnd.choice([[], [], [6], [3, 9], [12]]),
        "budget_inr": rnd.choice([200000, 300000, 450000, 700000, 1200000]),
    }


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_fuzz_three_packages_are_always_valid_and_within_budget(cat, seed):
    rnd = random.Random(seed)
    client = TestClient(create_app(db_path=Path(tempfile.mkdtemp()) / "f.sqlite"))
    seen = 0
    for _ in range(40):
        body = random_request(rnd, cat)
        j = client.post("/api/packages/variants", json=body).json()
        if j["outcome"] != "VARIANTS":
            assert j["outcome"] in ("OVER_BUDGET", "NO_PACKAGE")
            continue
        seen += 1
        pk = {k: p for k, p in j["variants"].items() if p}
        assert set(pk) == {"cheapest", "fastest", "best_rated"}
        for name, p in pk.items():
            assert validate_trip(to_trip_format(p), cat) == [], (name, body)
            assert p["pricing"]["total_inr"] <= body["budget_inr"], (name, body)
        cheapest = pk["cheapest"]["pricing"]["total_inr"]
        assert cheapest <= min(p["pricing"]["total_inr"] for p in pk.values())
        assert pk["fastest"]["metrics"]["transit_minutes"] <= min(p["metrics"]["transit_minutes"] for p in pk.values())
        assert pk["best_rated"]["metrics"]["avg_hotel_stars"] >= max(p["metrics"]["avg_hotel_stars"] for p in pk.values())
        if j["recommended"]:
            assert cheapest <= j["recommended"]["pricing"]["total_inr"]
    assert seen >= 8


@pytest.mark.parametrize("seed", [21, 22])
def test_fuzz_every_city_plan_option_gives_the_promised_price(cat, seed):
    """An option's price must equal what applying it gives, on an unchanged package.

    (Options describe the package as it is NOW; after any change they must be fetched again, so each
    option here is applied to a freshly built, identical package.)
    """
    rnd = random.Random(seed)
    client = TestClient(create_app(db_path=Path(tempfile.mkdtemp()) / "f.sqlite"))
    checked = 0
    for _ in range(14):
        body = random_request(rnd, cat)
        j = client.post("/api/packages", json=body).json()
        if j["outcome"] != "PACKAGE":
            continue
        opts = client.get(f"/api/packages/{j['package']['package_id']}/options/city-plans").json()["options"]
        for o in rnd.sample(opts, min(4, len(opts))):
            pkg = client.post("/api/packages", json=body).json()["package"]            # identical, unchanged package
            r = client.post(f"/api/packages/{pkg['package_id']}/changes",
                            json={"op": "CHANGE_CITY_PLAN", "plan": o["plan"], "raise_budget": True}).json()
            assert r["result"] == "APPLIED", (o, r)
            assert r["package"]["pricing"]["total_inr"] == o["total_inr"], (body, o)
            assert validate_trip(to_trip_format(r["package"]), cat) == []
            checked += 1
    assert checked >= 10


def test_fuzz_a_stream_of_bookings_never_sells_a_seat_or_room_twice(cat):
    """Simulate many travelers booking one after another and several racing with stale packages."""
    rnd = random.Random(99)
    client = TestClient(create_app(db_path=Path(tempfile.mkdtemp()) / "s2.sqlite"))
    store = cast(FastAPI, client.app).state.store
    booked = conflicts = 0
    stale = []
    for n in range(70):
        body = random_request(rnd, cat)
        body.update(departure_city="Bengaluru", country="Japan", budget_inr=500000)      # one busy corner of the catalog
        body["start_date"] = (date(2027, 4, 3) + timedelta(days=rnd.randint(0, 6))).isoformat()
        body["nights"] = 4
        j = client.post("/api/packages", json=body).json()
        if j["outcome"] != "PACKAGE":
            continue
        pkg = j["package"]
        if n % 5 == 0:
            stale.append(pkg["package_id"])             # built now, booked later (inventory may be gone by then)
            continue
        r = client.post(f"/api/packages/{pkg['package_id']}/confirm")
        assert r.status_code in (200, 409)
        booked += r.status_code == 200
        conflicts += r.status_code == 409
    for pid in stale:
        r = client.post(f"/api/packages/{pid}/confirm")
        assert r.status_code in (200, 409)
        booked += r.status_code == 200
        conflicts += r.status_code == 409
    seats, rooms = store.used_maps()
    for fid, used in seats.items():                      # never oversold
        assert used <= cat.flights[fid]["seats_left"], fid
    for (room_id, day), used in rooms.items():
        assert used <= cat.rooms_left(room_id, day), (room_id, day)
    assert booked >= 5
    # every booked reservation is a valid package
    with store._connect() as con:                        # noqa: SLF001 (test peeks at the database)
        rows = con.execute("SELECT snapshot_json FROM reservations").fetchall()
    import json
    assert len(rows) == booked
    for row in rows:
        assert validate_trip(to_trip_format(json.loads(row["snapshot_json"])), cat) == []
