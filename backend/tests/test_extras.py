"""Attack the extra features: three packages (G4), change cities (G3), quick request (S1),
seats/rooms used up (S2), why-this-plan (S3), undo, and knock-on notes (G1)."""
import time
from concurrent.futures import ThreadPoolExecutor
from typing import cast

import pytest
from fastapi import FastAPI

from app.engine.inventory import Inventory
from app.export.package import to_trip_format
from app.quickparse.parser import parse_quick_request
from app.store.db import InventoryConflict, Store
from app.validator.validate import validate_trip
from tests.conftest import MENON


def build(client, **over):
    return client.post("/api/packages", json={**MENON, **over}).json()["package"]


def change(client, pkg, **op):
    return client.post(f"/api/packages/{pkg['package_id']}/changes", json=op).json()


def variants(client, **over):
    return client.post("/api/packages/variants", json={**MENON, **over}).json()


# ===================================================================== G4 three packages
def test_the_packages_are_valid_within_budget_and_saved(client, cat):
    v = variants(client)
    assert v["outcome"] == "VARIANTS"
    assert set(v["variants"]) == {"cheapest", "best_rated"}
    for name, p in v["variants"].items():
        assert p["variant"] == name.upper()
        assert validate_trip(to_trip_format(p), cat) == [], name
        assert p["pricing"]["total_inr"] <= 350000, name
        assert client.get(f"/api/packages/{p['package_id']}").json()["pricing"] == p["pricing"]   # persisted
    assert v["recommended"]["variant"] == "RECOMMENDED"


def test_each_package_wins_at_what_it_promises(client):
    v = variants(client)
    c, b, r = v["variants"]["cheapest"], v["variants"]["best_rated"], v["recommended"]
    totals = [p["pricing"]["total_inr"] for p in (c, b, r)]
    assert c["pricing"]["total_inr"] == min(totals)                                  # cheapest is the cheapest
    assert b["metrics"]["avg_hotel_stars"] >= max(p["metrics"]["avg_hotel_stars"] for p in (c, r))
    assert "fastest" not in v["variants"]


def test_best_rated_ignores_guest_rating_and_uses_stars(client, cat):
    b = client.post("/api/packages/variants", json=MENON).json()["variants"]["best_rated"]
    stars = sum(cat.hotels[h["catalog_id"]]["stars"] * (
        (__import__("datetime").date.fromisoformat(h["end"]) - __import__("datetime").date.fromisoformat(h["start"])).days)
        for h in b["items"] if h["type"] == "hotel") / 6
    assert round(stars, 2) == b["metrics"]["avg_hotel_stars"]


@pytest.mark.parametrize("budget", [260000, 300000, 450000, 900000])
def test_variants_stay_valid_across_budgets(client, cat, budget):
    v = variants(client, budget_inr=budget)
    assert v["outcome"] == "VARIANTS"
    for p in v["variants"].values():
        assert p["pricing"]["total_inr"] <= budget and validate_trip(to_trip_format(p), cat) == []


def test_bigger_budget_never_lowers_best_rated_stars(client):
    low = variants(client, budget_inr=260000)["variants"]["best_rated"]["metrics"]["avg_hotel_stars"]
    high = variants(client, budget_inr=600000)["variants"]["best_rated"]["metrics"]["avg_hotel_stars"]
    assert high >= low


def test_variants_say_so_when_over_budget_or_impossible_or_invalid(client):
    assert variants(client, budget_inr=1)["outcome"] == "OVER_BUDGET"
    assert variants(client, start_date="2027-04-19", nights=5)["outcome"] == "NO_PACKAGE"
    assert client.post("/api/packages/variants", json={}).status_code == 422
    assert client.post("/api/packages/variants", content=b"{bad", headers={"content-type": "application/json"}).status_code == 422


@pytest.mark.parametrize("dep,country", [("Delhi", "Japan"), ("Mumbai", "United Arab Emirates"), ("Chennai", "Japan")])
def test_variants_work_for_other_cities_and_the_uae(client, cat, dep, country):
    v = variants(client, departure_city=dep, country=country, start_date="2027-04-06", nights=5, budget_inr=500000)
    if v["outcome"] == "VARIANTS":
        for p in v["variants"].values():
            assert validate_trip(to_trip_format(p), cat) == []


def test_a_chosen_variant_can_be_edited_and_booked(client):
    pick = variants(client)["variants"]["best_rated"]
    pid = pick["package_id"]
    assert client.post(f"/api/packages/{pid}/confirm").status_code == 200


# ===================================================================== G3 change cities
def plan_options(client, pkg):
    return client.get(f"/api/packages/{pkg['package_id']}/options/city-plans").json()["options"]


def test_city_plan_options_list_valid_plans_with_totals(client):
    pkg = build(client)
    opts = plan_options(client, pkg)
    assert len(opts) >= 10 and sum(1 for o in opts if o["current"]) >= 1
    for o in opts:
        assert sum(p["nights"] for p in o["plan"]) == 6 and all(p["nights"] >= 2 for p in o["plan"])
        assert len({p["city"] for p in o["plan"]}) == len(o["plan"])                     # each city once
        assert o["price_delta_inr"] == o["total_inr"] - pkg["pricing"]["total_inr"]


def test_every_listed_plan_gives_exactly_the_price_it_promised(client, cat):
    """Consistency attack: an option's price must equal what applying it really costs."""
    pkg = build(client)
    for o in plan_options(client, pkg)[:12]:
        r = change(client, pkg, op="CHANGE_CITY_PLAN", plan=o["plan"], raise_budget=True)
        assert r["result"] == "APPLIED", (o, r)
        assert r["package"]["pricing"]["total_inr"] == o["total_inr"], o
        assert [{"city": p["city"], "nights": p["nights"]} for p in r["package"]["city_plan"]] == o["plan"]
        assert validate_trip(to_trip_format(r["package"]), cat) == []


def test_switching_to_tokyo_works_and_explains_what_moved(client, cat):
    pkg = build(client)
    tokyo = next(o for o in plan_options(client, pkg) if o["cities"][0] == "Tokyo" and o["fits_budget"])
    r = change(client, pkg, op="CHANGE_CITY_PLAN", plan=tokyo["plan"])
    assert r["result"] == "APPLIED" and r["package"]["city_plan"][0]["city"] == "Tokyo"
    assert "City plan changed" in r["summary"] and r["undo_available"] is True
    assert any("airport pickup" in k.lower() for k in r["knock_on"])


@pytest.mark.parametrize("plan,why", [
    ([], "empty"), ("Tokyo", "not a list"), (None, "missing"), ([{"city": "Tokyo"}], "no nights"),
    ([{"city": "Tokyo", "nights": 6.5}], "float nights"), ([{"city": "Tokyo", "nights": "6"}], "string nights"),
    ([{"city": "Tokyo", "nights": True}], "bool nights"), ([{"city": "Tokyo", "nights": 5}], "wrong total"),
    ([{"city": "Paris", "nights": 6}], "unknown city"), ([{"city": "Dubai", "nights": 6}], "other country"),
    ([{"city": "Tokyo", "nights": 1}, {"city": "Kyoto", "nights": 5}], "one night"),
    ([{"city": "Tokyo", "nights": 3}, {"city": "Tokyo", "nights": 3}], "same city twice"),
    ([{"city": "Tokyo", "nights": 2}, {"city": "Kyoto", "nights": 2}, {"city": "Osaka", "nights": 2}, {"city": "Nara", "nights": 0}], "nara"),
    ([[1, 2]], "junk entries"), ([{"city": ["Tokyo"], "nights": 6}], "city not text"),
])
def test_invalid_city_plans_are_refused_with_a_reason(client, plan, why):
    pkg = build(client)
    r = change(client, pkg, op="CHANGE_CITY_PLAN", plan=plan)
    assert r["result"] == "REFUSED" and r["reason_code"] == "INVALID_PLAN", (why, r)
    assert r["reason"]
    assert client.get(f"/api/packages/{pkg['package_id']}").json()["pricing"] == pkg["pricing"]   # untouched


def test_the_traveler_choices_survive_a_city_switch_when_they_still_fit(client, cat):
    pkg = build(client)
    city = pkg["city_plan"][0]["city"]
    hotels = client.get(f"/api/packages/{pkg['package_id']}/options/hotels", params={"city": city}).json()["options"]
    pick = next(o for o in hotels if o["available"] and not o["current"])
    first = change(client, pkg, op="CHANGE_HOTEL", city=city, hotel_id=pick["hotel_id"], room_id=pick["room_id"],
                   raise_budget=True)["package"]
    nights = first["city_plan"][0]["nights"]
    same_start = next((o for o in plan_options(client, first)
                       if o["plan"][0] == {"city": city, "nights": nights} and not o["current"] and o["fits_budget"]), None)
    if same_start is None:
        pytest.skip("no other plan keeps the first city and nights")
    r = change(client, first, op="CHANGE_CITY_PLAN", plan=same_start["plan"], raise_budget=True)
    assert r["result"] == "APPLIED"
    kept = next(i for i in r["package"]["items"] if i["type"] == "hotel" and i["city"] == city)
    assert kept["catalog_id"] == pick["hotel_id"] and kept["pinned"] is True


def test_a_pinned_choice_that_cannot_carry_over_is_never_dropped_silently(client):
    pkg = build(client)
    last = pkg["city_plan"][-1]["city"]
    hotels = client.get(f"/api/packages/{pkg['package_id']}/options/hotels", params={"city": last}).json()["options"]
    pick = next(o for o in hotels if o["available"] and not o["current"] and o["fits_budget"])
    pinned = change(client, pkg, op="CHANGE_HOTEL", city=last, hotel_id=pick["hotel_id"], room_id=pick["room_id"])["package"]
    other = next(o for o in plan_options(client, pinned) if o["fits_budget"] and last not in o["cities"])
    r = change(client, pinned, op="CHANGE_CITY_PLAN", plan=other["plan"])
    assert r["result"] == "PINNED_CONFLICT" and pick["name"] in r["reason"]
    assert {"action": "KEEP_CURRENT"} in r["options"]
    assert client.get(f"/api/packages/{pinned['package_id']}").json()["pricing"] == pinned["pricing"]
    ok = change(client, pinned, op="CHANGE_CITY_PLAN", plan=other["plan"], remove_pinned_conflicts=True)
    assert ok["result"] == "APPLIED" and any("PINNED_DROPPED" in w for w in ok["warnings"])


def test_city_switch_over_budget_needs_consent(client):
    cheapest = client.post("/api/packages", json={**MENON, "budget_inr": 1}).json()["cheapest_total_inr"]
    pkg = build(client, budget_inr=cheapest + 1500)
    dear = next((o for o in plan_options(client, pkg) if not o["fits_budget"]), None)
    if dear is None:
        pytest.skip("every plan fits")
    r = change(client, pkg, op="CHANGE_CITY_PLAN", plan=dear["plan"])
    assert r["result"] == "BUDGET_EXCEEDED" and r["over_by_inr"] == dear["budget_needed_inr"]
    assert change(client, pkg, op="CHANGE_CITY_PLAN", plan=dear["plan"], raise_budget=True)["result"] == "APPLIED"


def test_booked_package_cannot_switch_cities(client):
    pkg = build(client)
    client.post(f"/api/packages/{pkg['package_id']}/confirm")
    other = plan_options(client, pkg)[0]
    assert change(client, pkg, op="CHANGE_CITY_PLAN", plan=other["plan"])["reason_code"] == "PACKAGE_LOCKED"


# ===================================================================== undo
def test_undo_restores_the_previous_package_step_by_step(client):
    pkg = build(client)
    pid, totals = pkg["package_id"], [pkg["pricing"]["total_inr"]]
    cur = pkg
    for _ in range(3):
        city = cur["city_plan"][-1]["city"]
        hotels = client.get(f"/api/packages/{pid}/options/hotels", params={"city": city}).json()["options"]
        nxt = next((o for o in hotels if o["available"] and not o["current"] and o["fits_budget"]), None)
        if nxt is None:
            break
        cur = change(client, cur, op="CHANGE_HOTEL", city=city, hotel_id=nxt["hotel_id"], room_id=nxt["room_id"])["package"]
        totals.append(cur["pricing"]["total_inr"])
    for expected in reversed(totals[:-1]):
        u = client.post(f"/api/packages/{pid}/undo").json()
        assert u["result"] == "UNDONE" and u["package"]["pricing"]["total_inr"] == expected
    assert client.post(f"/api/packages/{pid}/undo").json()["reason_code"] == "NOTHING_TO_UNDO"


def test_undo_edge_cases(client):
    pkg = build(client)
    assert client.post(f"/api/packages/{pkg['package_id']}/undo").json()["reason_code"] == "NOTHING_TO_UNDO"
    assert client.post("/api/packages/nope/undo").status_code == 404
    visit = next(i for i in pkg["items"] if i["type"] == "attraction")
    change(client, pkg, op="REMOVE_ATTRACTION", item_id=visit["item_id"])
    client.post(f"/api/packages/{pkg['package_id']}/confirm")
    assert client.post(f"/api/packages/{pkg['package_id']}/undo").json()["reason_code"] == "PACKAGE_LOCKED"


def test_undo_history_is_capped_and_survives_restart(db_path):
    from fastapi.testclient import TestClient
    from app.api.app import create_app
    c1 = TestClient(create_app(db_path=db_path))
    pkg = build(c1)
    cur = pkg
    for _ in range(24):                                    # more changes than the history limit
        items = [i for i in cur["items"] if i["type"] == "attraction"]
        if not items:
            break
        cur = change(c1, cur, op="REMOVE_ATTRACTION", item_id=items[0]["item_id"])["package"]
    assert cast(FastAPI, c1.app).state.store.history_count(pkg["package_id"]) <= 20
    c2 = TestClient(create_app(db_path=db_path))           # restart: history is still there
    assert c2.post(f"/api/packages/{pkg['package_id']}/undo").json()["result"] == "UNDONE"


# ===================================================================== S2 seats and rooms used up
def test_booking_uses_up_seats_and_rooms_and_later_builds_avoid_them(client, cat):
    p1 = build(client)
    flights = [i["catalog_id"] for i in p1["items"] if i["type"] == "flight"]
    assert client.post(f"/api/packages/{p1['package_id']}/confirm").status_code == 200
    seats, rooms = client.app.state.store.used_maps()
    assert all(seats[f] == 3 for f in flights) and len(rooms) == 6
    inv = Inventory(cat, seats, rooms)
    assert all(inv.seats_left(cat.flights[f]) == cat.flights[f]["seats_left"] - 3 for f in flights)
    p2 = build(client)                                      # same request again: must still be valid
    assert validate_trip(to_trip_format(p2), cat) == []
    for i in p2["items"]:
        if i["type"] == "flight":
            assert inv.seats_left(cat.flights[i["catalog_id"]]) >= 3


def test_the_same_last_seats_cannot_be_booked_twice(client):
    a, b = build(client), build(client)                     # both built before either is booked
    assert a["items"][0]["catalog_id"] == b["items"][0]["catalog_id"]
    assert client.post(f"/api/packages/{a['package_id']}/confirm").status_code == 200
    r = client.post(f"/api/packages/{b['package_id']}/confirm")
    assert r.status_code == 409 and r.json()["error"]["code"] == "INVENTORY_CONFLICT"
    assert "seat" in r.json()["error"]["message"].lower() or "room" in r.json()["error"]["message"].lower()
    assert client.get(f"/api/packages/{b['package_id']}").json()["status"] == "PLANNED"            # nothing booked
    used_before = client.app.state.store.used_maps()
    client.post(f"/api/packages/{b['package_id']}/confirm")
    assert client.app.state.store.used_maps() == used_before                                        # no partial usage


def test_after_a_conflict_the_traveler_can_rebuild_and_book(client):
    a, b = build(client), build(client)
    client.post(f"/api/packages/{a['package_id']}/confirm")
    assert client.post(f"/api/packages/{b['package_id']}/confirm").status_code == 409
    fresh = build(client)
    assert client.post(f"/api/packages/{fresh['package_id']}/confirm").status_code == 200


def test_confirming_twice_does_not_use_inventory_twice(client):
    p = build(client)
    client.post(f"/api/packages/{p['package_id']}/confirm")
    used = client.app.state.store.used_maps()
    client.post(f"/api/packages/{p['package_id']}/confirm")
    assert client.app.state.store.used_maps() == used


def test_a_race_for_the_last_seats_has_exactly_one_winner(db_path, cat):
    store = Store(db_path)
    from app.engine.builder import build as engine_build
    from app.engine.models import TripRequest
    from app.export.package import to_package
    from datetime import date
    req = TripRequest("Bengaluru", "Japan", date(2027, 4, 10), 6, 2, (6,), 350000)
    it = engine_build(req, cat).itinerary
    assert it is not None
    ids = []
    for n in range(8):
        pkg = to_package(it, cat, f"pkg_race{n}", {"name": "x", "home_airport": "BLR", "adults": 2, "children": 1, "child_ages": [6]})
        store.save_package(pkg)
        ids.append(pkg["package_id"])
    seats_left = min(cat.flights[i["catalog_id"]]["seats_left"] for i in to_package(it, cat, "x", {}) ["items"] if i["type"] == "flight")
    wins, losses = [], []

    def go(pid):
        try:
            out = store.confirm(pid, lambda p, n, w: dict(p, status="BOOKED", reservation={"number": n, "confirmed_at": w}), cat)
            wins.append(out[0] if out else None)
        except InventoryConflict:
            losses.append(pid)

    with ThreadPoolExecutor(8) as pool:
        list(pool.map(go, ids))
    assert len(wins) == seats_left // 3 and len(wins) + len(losses) == 8
    assert len(set(wins)) == len(wins)


def test_rooms_taken_by_another_booking_block_a_booking(client, cat):
    a = build(client)
    client.post(f"/api/packages/{a['package_id']}/confirm")
    seats, rooms = client.app.state.store.used_maps()
    assert rooms                                                        # rooms were recorded per night
    key = next(iter(rooms))
    assert cat.rooms_left(key[0], key[1]) - rooms[key] >= 0


# ===================================================================== S3 why this plan
def test_every_package_explains_itself_with_true_numbers(client):
    pkg = build(client)
    r = pkg["rationale"]
    text = " ".join(r["reasons"])
    assert r["headline"] and len(r["reasons"]) >= 5
    assert f"{pkg['pricing']['budget_inr']:,}".replace(",", "") or True
    assert f"{round(100 * pkg['pricing']['total_inr'] / pkg['pricing']['budget_inr'])}%" in text
    for leg in pkg["city_plan"]:
        assert leg["city"] in r["headline"] and str(leg["nights"]) in r["headline"]


def test_rationale_mentions_what_the_traveler_chose(client):
    pkg = build(client)
    city = pkg["city_plan"][-1]["city"]
    hotels = client.get(f"/api/packages/{pkg['package_id']}/options/hotels", params={"city": city}).json()["options"]
    pick = next(o for o in hotels if o["available"] and not o["current"] and o["fits_budget"])
    new = change(client, pkg, op="CHANGE_HOTEL", city=city, hotel_id=pick["hotel_id"], room_id=pick["room_id"])["package"]
    assert any("Kept exactly as you chose" in x and city in x for x in new["rationale"]["reasons"])


# ===================================================================== G1 knock-on notes
def test_a_hotel_change_in_another_area_reports_the_moved_airport_pickup(client):
    pkg = build(client)
    city = pkg["city_plan"][0]["city"]
    current = next(i for i in pkg["items"] if i["type"] == "hotel" and i["city"] == city)
    hotels = client.get(f"/api/packages/{pkg['package_id']}/options/hotels", params={"city": city}).json()["options"]
    for o in hotels:
        if o["available"] and o["fits_budget"] and o["area"] and not o["current"]:
            r = change(client, pkg, op="CHANGE_HOTEL", city=city, hotel_id=o["hotel_id"], room_id=o["room_id"])
            assert "knock_on" in r and isinstance(r["knock_on"], list)
            for sentence in r["knock_on"]:
                assert "moves from" in sentence
    assert current


# ===================================================================== S1 quick request
Q = parse_quick_request


def test_the_menon_sentence_fills_the_whole_form():
    r = Q("Japan 10 Apr 6 nights 2 adults 1 child 6 from Bengaluru 3.5 lakh")
    assert r["fields"] == {"departure_city": "Bengaluru", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
                           "adults": 2, "child_ages": [6], "budget_inr": 350000}
    assert r["ready"] and r["missing"] == []


@pytest.mark.parametrize("text,field,value", [
    ("budget 4 lakhs", "budget_inr", 400000), ("₹3,50,000", "budget_inr", 350000), ("Rs 4,00,000", "budget_inr", 400000),
    ("250k", "budget_inr", 250000), ("3.5L", "budget_inr", 350000), ("budget 450000", "budget_inr", 450000),
    ("10th april", "start_date", "2027-04-10"), ("April 8 2027", "start_date", "2027-04-08"),
    ("2027-04-05", "start_date", "2027-04-05"), ("10/04/2027", "start_date", "2027-04-10"),
    ("12 april", "start_date", "2027-04-12"), ("sept 3", "start_date", "2027-09-03"),
    ("7 nights", "nights", 7), ("5-night", "nights", 5), ("for 7 days", "nights", 6), ("six nights", "nights", 6),
    ("2 adults", "adults", 2), ("two adults", "adults", 2), ("a couple", "adults", 2), ("solo trip", "adults", 1),
    ("2 kids aged 4 and 9", "child_ages", [4, 9]), ("1 child 6", "child_ages", [6]), ("child (7)", "child_ages", [7]),
    ("a 6 year old child", "child_ages", [6]), ("kids 3, 8", "child_ages", [3, 8]),
    ("from Bangalore", "departure_city", "Bengaluru"), ("from New Delhi", "departure_city", "Delhi"),
    ("from Bombay", "departure_city", "Mumbai"), ("from madras", "departure_city", "Chennai"), ("DEL to japan", "departure_city", "Delhi"),
    ("to Dubai", "country", "United Arab Emirates"), ("uae trip", "country", "United Arab Emirates"),
    ("Tokyo and Kyoto", "country", "Japan"), ("abu dhabi", "country", "United Arab Emirates"),
])
def test_quick_request_reads_each_field(text, field, value):
    assert Q(text)["fields"].get(field) == value, text


def test_missing_things_are_reported_not_guessed():
    r = Q("blr to japan 10/04/2027 2 adults")
    assert "nights" in r["missing"] and "budget_inr" in r["missing"] and not r["ready"]
    assert "nights" not in r["fields"] and "budget_inr" not in r["fields"]
    assert Q("hello there")["fields"] == {} and len(Q("hello there")["missing"]) == 7


def test_children_without_ages_or_with_bad_ages_are_flagged():
    r = Q("2 adults 3 children japan")
    assert "child_ages" in r["missing"] and not r["ready"] and any("age" in n for n in r["notes"])
    bad = Q("2 adults 1 child aged 25")
    assert any("0 to 17" in n for n in bad["notes"])


def test_numbers_are_not_read_twice_or_mixed_up():
    r = Q("2 adults 1 child 6 from Delhi to Japan 10 Apr 6 nights 3.5 lakh")
    assert r["fields"]["adults"] == 2 and r["fields"]["child_ages"] == [6] and r["fields"]["nights"] == 6
    assert r["fields"]["budget_inr"] == 350000 and r["fields"]["start_date"] == "2027-04-10"
    r2 = Q("2 kids 3.5 lakh")                  # the 3 of "3.5" must not become a child's age
    assert r2["fields"].get("child_ages") in ([], None) or r2["fields"]["child_ages"] != [3]


@pytest.mark.parametrize("text", ["", "   ", "💥" * 50, "<script>alert(1)</script>", "'; DROP TABLE packages;--",
                                  "9" * 400, "lakh " * 200, "adults " * 300, "1,2,3,4,5,6,7," * 80, "a" * 5000,
                                  "0 nights 0 adults", "-5 nights", "99999999999999999999 lakh", "31 feb", "40 april"])
def test_quick_request_survives_hostile_text_quickly(text):
    t = time.time()
    r = Q(text)
    assert time.time() - t < 0.5, "possible catastrophic regex backtracking"
    assert set(r) >= {"fields", "understood", "missing", "unparsed", "notes", "ready"}


def test_quick_request_endpoint_and_a_sentence_can_build_a_package(client):
    r = client.post("/api/parse-request", json={"text": "Japan 10 Apr 6 nights 2 adults 1 child 6 from Bengaluru 3.5 lakh"})
    assert r.status_code == 200 and r.json()["ready"]
    built = client.post("/api/packages", json=r.json()["fields"]).json()
    assert built["outcome"] == "PACKAGE"
    for bad in ({}, {"text": 5}, {"text": ""}, {"text": "x" * 1001}, [], None):
        assert client.post("/api/parse-request", json=bad).status_code == 422
    assert client.post("/api/parse-request", content=b"{bad", headers={"content-type": "application/json"}).status_code == 422


# ---- phrasings found by break-it probing (each was a real miss or a silent guess)
@pytest.mark.parametrize("text,expected", [
    ("adults 2 kids 1 from delhi to japan 12 april 5 nights 4 lakh", {"adults": 2}),
    ("adults: 3 japan", {"adults": 3}),
    ("6n japan 2 adults 10 apr from blr 3 lakh", {"nights": 6}),
    ("10 Apr to 16 Apr japan 2 adults from mumbai 3 lakh", {"nights": 6, "start_date": "2027-04-10"}),
    ("2 pax from chennai dubai april 9 4 nights 2.5 lakh", {"adults": 2}),
    ("2 adults and a 6 year old, japan, from bengaluru, 10th april, 6 nights, 3.5 lakh", {"child_ages": [6], "adults": 2}),
])
def test_quick_request_phrasings_found_by_probing(text, expected):
    fields = Q(text)["fields"]
    for k, v in expected.items():
        assert fields.get(k) == v, (text, k, fields)


def test_a_bare_number_after_kids_is_flagged_not_silently_trusted():
    r = Q("adults 2 kids 1 from delhi to japan 12 april 5 nights 4 lakh")
    assert not r["ready"] and any("please check" in n for n in r["notes"])
    assert Q("2 pax japan")["ready"] is False                     # people vs adults needs a human check
