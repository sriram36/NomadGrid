"""Golden Menon package + validator mutation tests (corrupt one thing, expect exactly that rule)."""
import copy
from datetime import datetime, timedelta

import pytest

from app.export.package import to_trip_format
from app.validator.validate import validate_trip


def rules(trip, cat, first=False):
    return {v.rule_id for v in validate_trip(trip, cat, first_package=first)}


@pytest.fixture()
def trip(golden):
    return to_trip_format(copy.deepcopy(golden))


def find(trip, type_, **kw):
    return [i for i in trip["items"] if i["type"] == type_ and all(i.get(k) == v for k, v in kw.items())]


# ----------------------------------------------------------------- golden
def test_menon_package_is_valid_within_budget_and_near_it(golden, cat):
    trip = to_trip_format(golden)
    assert validate_trip(trip, cat, first_package=True) == []
    p = golden["pricing"]
    assert p["total_inr"] <= 350000 and not p["over_budget"]
    assert p["total_inr"] >= 0.8 * 350000            # built NEAR the budget, not the cheapest package


def test_menon_never_uses_the_flight_with_too_few_seats(golden):
    ids = {i["catalog_id"] for i in golden["items"] if i["type"] == "flight"}
    assert "FL-403" not in ids                       # only 2 seats left, family of 3
    assert len(ids) == 2


def test_menon_has_one_to_two_attractions_on_every_full_day(golden):
    for d in golden["days"]:
        n = sum(1 for e in d["events"] if e["type"] == "attraction")
        if d["kind"] == "FULL":
            assert 1 <= n <= 2, d
        if d["kind"] == "LAST":
            assert n == 0


def test_every_item_has_the_shared_format_fields(golden):
    trip = to_trip_format(golden)
    for i in trip["items"]:
        for k in ["item_id", "type", "name", "city", "status", "catalog_id", "start", "end", "room_id",
                  "quantity", "price_inr", "booking", "sources", "warnings"]:
            assert k in i
        assert i["sources"] == []
    assert trip["country"] == "Japan" and trip["total_inr"] == sum(i["price_inr"] for i in trip["items"])
    assert all(h["room_id"] for h in trip["items"] if h["type"] == "hotel")


# ----------------------------------------------------------------- mutations: each must be caught
def mutate_and_expect(trip, cat, mutate, expected):
    t = copy.deepcopy(trip)
    mutate(t)
    got = rules(t, cat)
    assert expected in got, f"expected {expected}, got {sorted(got)}"


def test_catches_flight_with_too_few_seats(trip, cat):
    def m(t):
        f = find(t, "flight")[0]
        f["catalog_id"] = "FL-403"            # 2 seats left; also wrong times/airport
    mutate_and_expect(trip, cat, m, "F7")


def test_catches_arrival_on_wrong_date(trip, cat):
    def m(t):
        flights = find(t, "flight")
        flights[0]["catalog_id"] = "FL-405"   # lands 21:30 on 10 Apr: same date, so shift the trip instead
        t["start_date"] = "2027-04-11"
    mutate_and_expect(trip, cat, m, "F3")


def test_catches_changed_flight_time(trip, cat):
    def m(t):
        find(t, "flight")[0]["start"] = "2027-04-09T01:00"
    mutate_and_expect(trip, cat, m, "F1")


def test_catches_room_that_does_not_fit(trip, cat):
    def m(t):
        h = find(t, "hotel")[0]
        h["room_id"] = cat.rooms_of(h["catalog_id"])[0]["room_id"]
        for r in cat.rooms_of(h["catalog_id"]):
            if r["max_children"] == 0:
                h["room_id"] = r["room_id"]
        h["quantity"] = 1                      # one TWIN cannot hold 2 adults + a child
    mutate_and_expect(trip, cat, m, "H4")


def test_catches_room_of_another_hotel(trip, cat):
    def m(t):
        find(t, "hotel")[0]["room_id"] = "RM-OSA-010-A"
    mutate_and_expect(trip, cat, m, "H2")


def test_catches_sold_out_night(trip, cat):
    def m(t):
        h = find(t, "hotel")[0]
        h["quantity"] = 40                     # more rooms than any hotel has left
    mutate_and_expect(trip, cat, m, "H5")


def test_catches_gap_in_hotel_nights(trip, cat):
    def m(t):
        h = find(t, "hotel")[0]
        h["end"] = (datetime.fromisoformat(h["end"]) - timedelta(days=1)).date().isoformat()
    mutate_and_expect(trip, cat, m, "H3")


def test_catches_missing_airport_transfer(trip, cat):
    def m(t):
        first = min((i for i in t["items"] if i["type"] == "transfer" and cat.transfers[i["catalog_id"]].get("airport")),
                    key=lambda i: i["start"])
        t["items"].remove(first)
    mutate_and_expect(trip, cat, m, "A1")


def _airport_transfers(t, cat):
    out = [i for i in t["items"] if i["type"] == "transfer" and cat.transfers[i["catalog_id"]].get("airport")]
    return sorted(out, key=lambda i: i["start"])


def test_catches_pickup_less_than_60_minutes_after_landing(trip, cat):
    def m(t):
        a = _airport_transfers(t, cat)[0]
        landing = next(f for f in cat.flights.values() if f["flight_id"] == find(t, "flight")[0]["catalog_id"])["_arr"]
        a["start"] = (landing + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M")
    mutate_and_expect(trip, cat, m, "A4")


def test_catches_arriving_at_airport_less_than_180_minutes_before_departure(trip, cat):
    def m(t):
        d = _airport_transfers(t, cat)[1]
        f = cat.flights[find(t, "flight")[1]["catalog_id"]]
        d["start"] = (f["_dep"] - timedelta(minutes=170)).strftime("%Y-%m-%dT%H:%M")
    mutate_and_expect(trip, cat, m, "A5")


def test_catches_pickup_outside_service_hours(trip, cat):
    def m(t):
        d = _airport_transfers(t, cat)[1]
        d["start"] = d["start"][:11] + "03:00"
    mutate_and_expect(trip, cat, m, "A6")


def test_catches_departure_pickup_the_day_before(trip, cat):
    def m(t):
        d = _airport_transfers(t, cat)[1]
        d["start"] = "2027-04-15T21:00"
    mutate_and_expect(trip, cat, m, "A7")


def test_catches_missing_intercity_transfer(trip, cat):
    def m(t):
        t["items"] = [i for i in t["items"] if not (i["type"] == "transfer"
                                                   and cat.transfers[i["catalog_id"]].get("from_city"))]
    mutate_and_expect(trip, cat, m, "T1")


def test_catches_intercity_transfer_off_the_timetable(trip, cat):
    def m(t):
        x = next(i for i in t["items"] if i["type"] == "transfer" and cat.transfers[i["catalog_id"]].get("from_city"))
        x["start"] = x["start"][:11] + "08:07"
    mutate_and_expect(trip, cat, m, "T3")


def test_catches_attraction_in_wrong_city(trip, cat):
    def m(t):
        v = find(t, "attraction")[0]
        wrong = next(a for a in cat.attractions.values() if a["city"] == "Tokyo")
        v["catalog_id"] = wrong["attraction_id"]
    mutate_and_expect(trip, cat, m, "X2")


def test_catches_attraction_on_a_closed_date(trip, cat):
    def m(t):
        v = find(t, "attraction")[0]
        v["catalog_id"] = "ATT-TYO-006"       # Edo Craft Museum: closed on every date from 10 Apr
    mutate_and_expect(trip, cat, m, "X3")


def test_catches_visit_outside_opening_hours(trip, cat):
    def m(t):
        v = find(t, "attraction")[0]
        v["start"] = v["start"][:11] + "03:00"
        v["end"] = v["end"][:11] + "04:30"
    mutate_and_expect(trip, cat, m, "X4")


def test_catches_overlapping_visits(trip, cat):
    def m(t):
        by = {}
        for v in find(t, "attraction"):
            by.setdefault(v["start"][:10], []).append(v)
        two = next(l for l in by.values() if len(l) >= 2)
        two[1]["start"], two[1]["end"] = two[0]["start"], two[0]["end"]
    mutate_and_expect(trip, cat, m, "X5")


def test_catches_duplicate_attraction(trip, cat):
    def m(t):
        t["items"].append(copy.deepcopy(find(t, "attraction")[0]))
    mutate_and_expect(trip, cat, m, "X6")


def test_catches_attraction_on_last_day(trip, cat):
    def m(t):
        v = copy.deepcopy(find(t, "attraction")[0])
        v["start"], v["end"] = "2027-04-16T10:00", "2027-04-16T11:00"
        t["items"].append(v)
    mutate_and_expect(trip, cat, m, "X7")


def test_catches_visit_before_reaching_the_city(trip, cat):
    first_city = min(find(trip, "hotel"), key=lambda h: h["start"])["city"]
    used = {v["catalog_id"] for v in find(trip, "attraction")}
    rec = next(a for a in cat.attractions_in(first_city)
               if a["attraction_id"] not in used and a["open_from"] <= "07:00" and a["visit_minutes"] <= 120
               and "SAT" in a["open_days"] and "2027-04-10" not in a.get("closed_dates", []))

    def m(t):
        v = copy.deepcopy(find(t, "attraction")[0])
        v["catalog_id"] = rec["attraction_id"]
        v["city"] = first_city
        v["start"], v["end"] = "2027-04-10T07:00", f"2027-04-10T{(7 * 60 + rec['visit_minutes']) // 60:02d}:{(7 * 60 + rec['visit_minutes']) % 60:02d}"
        t["items"].append(v)
    mutate_and_expect(trip, cat, m, "X8")


def test_catches_wrong_price(trip, cat):
    def m(t):
        find(t, "flight")[0]["price_inr"] += 1
    mutate_and_expect(trip, cat, m, "P1")


def test_catches_wrong_total(trip, cat):
    def m(t):
        t["total_inr"] += 5
    mutate_and_expect(trip, cat, m, "P2")


def test_catches_too_many_nights(trip, cat):
    def m(t):
        t["end_date"] = "2027-04-25"
    mutate_and_expect(trip, cat, m, "D1")


def test_catches_return_after_data_window(trip, cat):
    def m(t):
        t["end_date"] = "2027-04-21"
    mutate_and_expect(trip, cat, m, "D3")


def test_catches_non_empty_sources(trip, cat):
    def m(t):
        t["items"][0]["sources"] = ["http://x"]
    mutate_and_expect(trip, cat, m, "E1")


def test_catches_partially_booked_package(trip, cat):
    def m(t):
        t["items"][0]["status"] = "BOOKED"
    mutate_and_expect(trip, cat, m, "E2")


def test_catches_city_visited_twice(trip, cat):
    def m(t):
        hs = sorted(find(t, "hotel"), key=lambda h: h["start"])
        hs[1]["city"] = hs[0]["city"]
        hs[1]["catalog_id"] = hs[0]["catalog_id"]
        hs[1]["room_id"] = hs[0]["room_id"]
    mutate_and_expect(trip, cat, m, "C3")


def test_catches_single_night_stay(trip, cat):
    def m(t):
        hs = sorted(find(t, "hotel"), key=lambda h: h["start"])
        hs[0]["end"] = (datetime.fromisoformat(hs[0]["start"]) + timedelta(days=1)).date().isoformat()
        hs[1]["start"] = hs[0]["end"]
    mutate_and_expect(trip, cat, m, "C2")


def test_validator_survives_garbage_input(cat):
    assert validate_trip({}, cat)[0].rule_id == "E1"
    assert validate_trip({"start_date": "x"}, cat)[0].rule_id == "E1"
    assert validate_trip({"start_date": "2027-04-10", "end_date": "2027-04-16",
                          "traveler": {"adults": 2, "children": 1, "home_airport": "BLR"},
                          "country": "Narnia", "items": []}, cat)[0].rule_id == "C1"
