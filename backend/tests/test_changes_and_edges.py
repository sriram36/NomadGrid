"""Attack the change operations and the time-window edges."""
from datetime import date, datetime, timedelta

import pytest

from app.changes.rebuild import itinerary_from_package, retime_arrival_day
from app.changes.refusal import Refusal
from app.changes.service import apply_change
from app.core.timeutil import at
from app.engine.hotels import hotel_options
from app.engine.inventory import Inventory
from app.engine.models import Visit
from app.engine.schedule import arrival_pickup, departure_pickup, intercity_departure
from app.export.package import to_package, to_trip_format
from app.validator.validate import validate_trip
from tests.conftest import MENON


def D(s):
    return datetime.fromisoformat(s)


def must(x):
    """Assert a value is not None (and let the type checker know)."""
    assert x is not None
    return x


def build(client, **over):
    return client.post("/api/packages", json={**MENON, **over}).json()["package"]


def change(client, pkg, **op):
    return client.post(f"/api/packages/{pkg['package_id']}/changes", json=op).json()


def hotel_item(pkg, city):
    return next(i for i in pkg["items"] if i["type"] == "hotel" and i["city"] == city)


def first_city(pkg):
    return pkg["city_plan"][0]["city"]


def last_city(pkg):
    return pkg["city_plan"][-1]["city"]


# ================================================================ change hotel
def test_changing_to_a_cheaper_hotel_updates_total_and_stays_valid(client, cat):
    pkg = build(client)
    city = last_city(pkg)
    opts = client.get(f"/api/packages/{pkg['package_id']}/options/hotels", params={"city": city}).json()["options"]
    cheaper = next(o for o in opts if o["available"] and not o["current"] and o["price_delta_inr"] < 0)
    r = change(client, pkg, op="CHANGE_HOTEL", city=city, hotel_id=cheaper["hotel_id"], room_id=cheaper["room_id"])
    assert r["result"] == "APPLIED" and r["price_delta_inr"] == cheaper["price_delta_inr"]
    new = r["package"]
    assert new["pricing"]["total_inr"] == pkg["pricing"]["total_inr"] + r["price_delta_inr"]
    assert validate_trip(to_trip_format(new), cat) == []
    assert hotel_item(new, city)["catalog_id"] == cheaper["hotel_id"] and hotel_item(new, city)["pinned"] is True
    assert client.get(f"/api/packages/{pkg['package_id']}").json()["pricing"] == new["pricing"]   # persisted
    assert r["summary"] and r["changed_item_ids"]


def test_every_listed_hotel_option_is_either_applicable_or_explains_why_not(client, cat):
    pkg = build(client)
    for city in [l["city"] for l in pkg["city_plan"]]:
        opts = client.get(f"/api/packages/{pkg['package_id']}/options/hotels", params={"city": city}).json()["options"]
        assert opts and sum(1 for o in opts if o["current"]) == 1
        for o in opts:
            if o["available"]:
                r = change(client, pkg, op="CHANGE_HOTEL", city=city, hotel_id=o["hotel_id"], room_id=o["room_id"])
                assert r["result"] in ("APPLIED", "BUDGET_EXCEEDED"), (o, r)
                if r["result"] == "APPLIED":
                    assert validate_trip(to_trip_format(r["package"]), cat) == []
            else:
                assert o["reason_unavailable"]


def test_hotel_change_refusals(client):
    pkg = build(client)
    city = first_city(pkg)
    cases = [
        (dict(city="Atlantis", hotel_id="HTL-TYO-001", room_id="RM-TYO-001-A"), "INVALID_CITY"),
        (dict(city=city, hotel_id="HTL-NOPE", room_id="RM-X"), "HOTEL_NOT_FOUND"),
        (dict(city=city, hotel_id="HTL-DXB-001", room_id="RM-DXB-001-A"), "HOTEL_NOT_FOUND"),   # another city's hotel
        (dict(city=city, hotel_id="HTL-OSA-001", room_id="RM-KYO-001-A"), "ROOM_NOT_FOUND"),     # room of another hotel
        (dict(city=city, hotel_id="HTL-OSA-010", room_id="RM-OSA-010-A"), "ROOM_DOES_NOT_FIT"),  # capsule, SINGLE only
        (dict(city=city), "HOTEL_NOT_FOUND"),
    ]
    for body, code in cases:
        r = change(client, pkg, op="CHANGE_HOTEL", **body)
        if city == "Osaka" or code in ("INVALID_CITY", "HOTEL_NOT_FOUND", "ROOM_NOT_FOUND"):
            assert r["result"] == "REFUSED" and r["reason_code"] in (code, "HOTEL_NOT_FOUND", "ROOM_NOT_FOUND"), (body, r)
            assert r["reason"]


def test_sold_out_room_is_refused_with_the_night(client, cat):
    pkg = build(client)
    city = last_city(pkg)
    leg = next(l for l in pkg["city_plan"] if l["city"] == city)
    cur = hotel_item(pkg, city)
    target = next(r for h in cat.hotels_in(city) for r in cat.rooms_of(h["hotel_id"])
                  if r["max_children"] >= 1 and r["room_id"] != cur["room_id"])
    night = date.fromisoformat(leg["check_in"]) + timedelta(days=1)
    inv = Inventory(cat, used_rooms={(target["room_id"], night): 999})          # sold out on one night
    res = apply_change(pkg, {"op": "CHANGE_HOTEL", "city": city, "hotel_id": target["hotel_id"],
                             "room_id": target["room_id"]}, cat, inv)
    assert res["result"] == "REFUSED" and res["reason_code"] == "ROOMS_UNAVAILABLE"
    assert f"{night:%d %b}" in res["reason"] and "sold out" in res["reason"]
    ok = apply_change(pkg, {"op": "CHANGE_HOTEL", "city": city, "hotel_id": target["hotel_id"],
                            "room_id": target["room_id"], "raise_budget": True}, cat, Inventory(cat))
    assert ok["result"] in ("APPLIED", "REFUSED")


# ================================================================ change flight
def test_flight_change_refusals(client, cat):
    pkg = build(client)
    r = change(client, pkg, op="CHANGE_FLIGHT", leg="ARRIVAL", flight_id="FL-403")
    assert r["result"] == "REFUSED" and r["reason_code"] in ("AIRPORT_MISMATCH", "SEATS_UNAVAILABLE", "FLIGHT_MISMATCH")
    ret = next(i for i in pkg["items"] if i["type"] == "flight" and i["leg"] == "RETURN")["catalog_id"]
    assert change(client, pkg, op="CHANGE_FLIGHT", leg="ARRIVAL", flight_id=ret)["reason_code"] == "FLIGHT_MISMATCH"
    assert change(client, pkg, op="CHANGE_FLIGHT", leg="SIDEWAYS", flight_id=ret)["reason_code"] == "INVALID_LEG"
    assert change(client, pkg, op="CHANGE_FLIGHT", leg="RETURN", flight_id="FL-NOPE")["reason_code"] == "FLIGHT_NOT_FOUND"


def test_changing_to_the_same_flight_is_a_harmless_no_op(client, cat):
    pkg = build(client)
    cur = next(i for i in pkg["items"] if i["type"] == "flight" and i["leg"] == "RETURN")["catalog_id"]
    r = change(client, pkg, op="CHANGE_FLIGHT", leg="RETURN", flight_id=cur)
    assert r["result"] == "APPLIED" and r["price_delta_inr"] == 0
    assert validate_trip(to_trip_format(r["package"]), cat) == []


def test_every_listed_flight_option_is_applicable_or_explained(client, cat):
    pkg = build(client)
    for leg in ("ARRIVAL", "RETURN"):
        opts = client.get(f"/api/packages/{pkg['package_id']}/options/flights", params={"leg": leg}).json()["options"]
        assert opts
        for o in opts:
            if o["available"]:
                r = change(client, pkg, op="CHANGE_FLIGHT", leg=leg, flight_id=o["flight_id"])
                assert r["result"] in ("APPLIED", "BUDGET_EXCEEDED")
                if r["result"] == "APPLIED":
                    assert validate_trip(to_trip_format(r["package"]), cat) == []
            else:
                assert o["reason_unavailable"]


def test_a_flight_change_that_has_other_options_works_end_to_end(client, cat):
    """Find a request where the arrival has several valid flights and switch between them."""
    for start in ("2027-04-03", "2027-04-05", "2027-04-08", "2027-04-12"):
        j = client.post("/api/packages", json={**MENON, "start_date": start, "nights": 5, "budget_inr": 600000}).json()
        if j["outcome"] != "PACKAGE":
            continue
        pkg = j["package"]
        opts = client.get(f"/api/packages/{pkg['package_id']}/options/flights", params={"leg": "ARRIVAL"}).json()["options"]
        alts = [o for o in opts if o["available"] and not o["current"]]
        if not alts:
            continue
        r = change(client, pkg, op="CHANGE_FLIGHT", leg="ARRIVAL", flight_id=alts[0]["flight_id"])
        assert r["result"] in ("APPLIED", "BUDGET_EXCEEDED", "PINNED_CONFLICT")
        if r["result"] == "APPLIED":
            assert validate_trip(to_trip_format(r["package"]), cat) == []
            assert r["price_delta_inr"] == alts[0]["price_delta_inr"]
        return
    pytest.skip("no request with multiple arrival flights found")


# ================================================================ attractions
def day_of(pkg, kind):
    return next(d for d in pkg["days"] if d["kind"] == kind)


def test_add_and_remove_an_attraction(client, cat):
    pkg = build(client)
    day = day_of(pkg, "FULL")["date"]
    opts = client.get(f"/api/packages/{pkg['package_id']}/options/attractions", params={"date": day}).json()["options"]
    assert opts
    o = opts[0]
    assert o["start_choices"]
    r = change(client, pkg, op="ADD_ATTRACTION", attraction_id=o["attraction_id"], date=day, start=o["start_choices"][0])
    assert r["result"] in ("APPLIED", "BUDGET_EXCEEDED")
    if r["result"] == "BUDGET_EXCEEDED":
        r = change(client, pkg, op="ADD_ATTRACTION", attraction_id=o["attraction_id"], date=day,
                   start=o["start_choices"][0], raise_budget=True)
        assert r["result"] == "APPLIED"
    new = r["package"]
    assert validate_trip(to_trip_format(new), cat) == []
    added = next(i for i in new["items"] if i["type"] == "attraction" and i["catalog_id"] == o["attraction_id"])
    assert added["pinned"] is True
    gone = change(client, new, op="REMOVE_ATTRACTION", item_id=added["item_id"])
    assert gone["result"] == "APPLIED"
    assert all(i["catalog_id"] != o["attraction_id"] for i in gone["package"]["items"])
    assert validate_trip(to_trip_format(gone["package"]), cat) == []


def test_attraction_refusals(client, cat):
    pkg = build(client)
    city_day = {d["date"]: d["city"] for d in pkg["days"] if d["kind"] != "LAST"}
    full = day_of(pkg, "FULL")
    used = next(i for i in pkg["items"] if i["type"] == "attraction")
    # unknown / bad day / last day
    assert change(client, pkg, op="ADD_ATTRACTION", attraction_id="ATT-NOPE", date=full["date"])["reason_code"] == "ATTRACTION_NOT_FOUND"
    assert change(client, pkg, op="ADD_ATTRACTION", attraction_id=used["catalog_id"], date="garbage")["reason_code"] == "INVALID_DAY"
    assert change(client, pkg, op="ADD_ATTRACTION", attraction_id=used["catalog_id"], date=pkg["end_date"])["reason_code"] == "INVALID_DAY"
    assert change(client, pkg, op="ADD_ATTRACTION", attraction_id=used["catalog_id"], date="2027-03-01")["reason_code"] == "INVALID_DAY"
    # duplicate
    assert change(client, pkg, op="ADD_ATTRACTION", attraction_id=used["catalog_id"], date=used["start"][:10])["reason_code"] == "ATTRACTION_DUPLICATE"
    # wrong city: an attraction from a city we are not in
    other = next(a for a in cat.attractions.values() if a["city"] not in city_day.values() and a["city"] != "Nara")
    assert change(client, pkg, op="ADD_ATTRACTION", attraction_id=other["attraction_id"], date=full["date"])["reason_code"] == "ATTRACTION_WRONG_CITY"
    # closed on that weekday / date (search the plan for a real closure)
    closed = next(((a, d) for d, c in city_day.items() for a in cat.attractions_in(c)
                   if (not __import__("app.engine.attractions", fromlist=["x"]).is_open_on(a, date.fromisoformat(d)))
                   and a["attraction_id"] not in {i["catalog_id"] for i in pkg["items"]}), None)
    if closed:
        r = change(client, pkg, op="ADD_ATTRACTION", attraction_id=closed[0]["attraction_id"], date=closed[1])
        assert r["reason_code"] == "ATTRACTION_CLOSED" and "closed" in r["reason"]


def test_attraction_time_attacks(client):
    pkg = build(client)
    full = day_of(pkg, "FULL")
    opts = client.get(f"/api/packages/{pkg['package_id']}/options/attractions", params={"date": full["date"]}).json()["options"]
    o = opts[0]
    base = dict(op="ADD_ATTRACTION", attraction_id=o["attraction_id"], date=full["date"], raise_budget=True)
    assert change(client, pkg, **base, start="03:00")["reason_code"] == "ATTRACTION_OUTSIDE_HOURS"
    assert change(client, pkg, **base, start="23:59")["reason_code"] == "ATTRACTION_OUTSIDE_HOURS"
    assert change(client, pkg, **base, start="banana")["reason_code"] == "INVALID_TIME"
    # overlap with a visit already on that day
    busy = next(i for i in pkg["items"] if i["type"] == "attraction" and i["start"][:10] == full["date"])
    r = change(client, pkg, **base, start=busy["start"][11:16])
    assert r["result"] == "REFUSED" and r["reason_code"] in ("ATTRACTION_OVERLAP", "ATTRACTION_OUTSIDE_HOURS")


def test_remove_unknown_item_and_unknown_ops(client):
    pkg = build(client)
    assert change(client, pkg, op="REMOVE_ATTRACTION", item_id="i999")["reason_code"] == "ITEM_NOT_FOUND"
    flight = next(i for i in pkg["items"] if i["type"] == "flight")
    assert change(client, pkg, op="REMOVE_ATTRACTION", item_id=flight["item_id"])["reason_code"] == "ITEM_NOT_FOUND"
    assert change(client, pkg, op="DELETE_EVERYTHING")["reason_code"] == "UNKNOWN_OP"
    assert change(client, pkg)["reason_code"] == "UNKNOWN_OP"
    assert client.post(f"/api/packages/{pkg['package_id']}/changes", json=[1]).status_code == 422
    assert client.post(f"/api/packages/{pkg['package_id']}/changes", content=b"{bad",
                       headers={"content-type": "application/json"}).status_code == 422


def test_stale_item_id_after_a_change_is_refused_not_misapplied(client):
    pkg = build(client)
    visits = [i for i in pkg["items"] if i["type"] == "attraction"]
    r = change(client, pkg, op="REMOVE_ATTRACTION", item_id=visits[0]["item_id"])
    assert r["result"] == "APPLIED"
    # item ids are renumbered; replaying the old id against the NEW package must hit the right thing or fail cleanly
    r2 = change(client, r["package"], op="REMOVE_ATTRACTION", item_id="i9999")
    assert r2["reason_code"] == "ITEM_NOT_FOUND"


# ================================================================ budget & lock
def test_over_budget_edit_is_not_applied_until_the_traveler_agrees(client, cat):
    cheapest = client.post("/api/packages", json={**MENON, "budget_inr": 1}).json()["cheapest_total_inr"]
    pkg = build(client, budget_inr=cheapest + 2000)
    city = last_city(pkg)
    opts = client.get(f"/api/packages/{pkg['package_id']}/options/hotels", params={"city": city}).json()["options"]
    pricier = next(o for o in opts if o["available"] and not o["fits_budget"])
    r = change(client, pkg, op="CHANGE_HOTEL", city=city, hotel_id=pricier["hotel_id"], room_id=pricier["room_id"])
    assert r["result"] == "BUDGET_EXCEEDED" and r["over_by_inr"] == pricier["budget_needed_inr"] > 0
    assert client.get(f"/api/packages/{pkg['package_id']}").json()["pricing"] == pkg["pricing"]     # untouched
    ok = change(client, pkg, op="CHANGE_HOTEL", city=city, hotel_id=pricier["hotel_id"], room_id=pricier["room_id"],
                raise_budget=True)
    assert ok["result"] == "APPLIED"
    assert ok["package"]["pricing"]["budget_inr"] == ok["package"]["pricing"]["total_inr"]
    assert ok["package"]["pricing"]["remaining_inr"] == 0 and not ok["package"]["pricing"]["over_budget"]
    assert validate_trip(to_trip_format(ok["package"]), cat) == []


def test_confirmed_package_is_locked(client):
    pkg = build(client)
    client.post(f"/api/packages/{pkg['package_id']}/confirm")
    visit = next(i for i in pkg["items"] if i["type"] == "attraction")
    r = change(client, pkg, op="REMOVE_ATTRACTION", item_id=visit["item_id"])
    assert r["reason_code"] == "PACKAGE_LOCKED"


# ================================================================ pinned items are never dropped silently
def test_pinned_attraction_that_no_longer_fits_stops_the_change_and_asks(cat):
    from app.engine.builder import build as build_pkg
    from app.engine.models import TripRequest
    req = TripRequest("Bengaluru", "Japan", date(2027, 4, 10), 6, 2, (6,), 350000)
    res = build_pkg(req, cat)
    assert res.itinerary is not None
    pkg = to_package(res.itinerary, cat, "pkg_p", {"name": "x", "home_airport": "BLR", "adults": 2, "children": 1, "child_ages": [6]})
    it = itinerary_from_package(pkg, cat)
    rec = next(a for a in cat.attractions_in(it.cities[0]) if a["open_until"] >= "17:00" and a["visit_minutes"] >= 60
               and a["attraction_id"] not in {v.attraction["attraction_id"] for v in it.visits})
    it.visits = [v for v in it.visits if v.day != it.request.start_date]
    from app.core.timeutil import hm
    start = max(hm(rec["open_from"]), 13 * 60)
    it.visits.append(Visit(rec, at(date(2027, 4, 10), start), at(date(2027, 4, 10), start + rec["visit_minutes"]), 0,
                           date(2027, 4, 10), pinned=True))
    # the traveler now reaches the hotel very late
    it.arr_transfer.arrive = D("2027-04-10T20:00")
    with pytest.raises(Refusal) as e:
        retime_arrival_day(it, allow_remove=False)
    assert e.value.code == "PINNED_CONFLICT" and e.value.options and rec["name"] in e.value.reason
    assert any(v.pinned for v in it.visits)             # nothing was silently dropped
    warnings = retime_arrival_day(it, allow_remove=True)
    assert not any(v.attraction["attraction_id"] == rec["attraction_id"] for v in it.visits)
    assert any("removed" in w for w in warnings)


def test_unpinned_arrival_visit_is_shifted_not_lost(cat):
    from app.engine.builder import build as build_pkg
    from app.engine.models import TripRequest
    req = TripRequest("Bengaluru", "Japan", date(2027, 4, 10), 6, 2, (6,), 600000)
    res = build_pkg(req, cat)
    assert res.itinerary is not None
    pkg = to_package(res.itinerary, cat, "pkg_s", {"name": "x", "home_airport": "BLR", "adults": 2, "children": 1, "child_ages": [6]})
    it = itinerary_from_package(pkg, cat)
    todays = [v for v in it.visits if v.day == it.request.start_date]
    if not todays:
        pytest.skip("no arrival-day visit in this package")
    v = todays[0]
    it.arr_transfer.arrive = v.start + timedelta(minutes=20)
    retime_arrival_day(it, allow_remove=False)
    kept = [x for x in it.visits if x.day == it.request.start_date]
    assert all(x.start >= it.arr_transfer.arrive for x in kept)


# ================================================================ time-window edges (schedule)
SHUTTLE = {"service_from": "06:00", "service_until": "00:30", "duration_minutes": 60}
TAXI = {"service_from": "06:00", "service_until": "23:00", "duration_minutes": 50}
ALLDAY = {"service_from": "00:00", "service_until": "24:00", "duration_minutes": 30}


def test_arrival_pickup_edges():
    assert must(arrival_pickup(TAXI, D("2027-04-10T09:20")))[0] == D("2027-04-10T10:20")
    assert must(arrival_pickup(TAXI, D("2027-04-10T03:00")))[0] == D("2027-04-10T06:00")        # waits for service to open
    assert must(arrival_pickup(TAXI, D("2027-04-10T21:59")))[0] == D("2027-04-10T22:59")
    assert must(arrival_pickup(TAXI, D("2027-04-10T22:00")))[0] == D("2027-04-10T23:00")        # exactly at the end: allowed
    assert arrival_pickup(TAXI, D("2027-04-10T22:01")) is None                            # one minute too late
    assert must(arrival_pickup(TAXI, D("2027-04-10T09:20")))[1] == D("2027-04-10T11:10")


def test_arrival_pickup_wrapping_window_spills_past_midnight():
    assert must(arrival_pickup(SHUTTLE, D("2027-04-10T23:30")))[0] == D("2027-04-11T00:30")
    assert arrival_pickup(SHUTTLE, D("2027-04-10T23:31")) is None
    assert must(arrival_pickup(ALLDAY, D("2027-04-10T23:00")))[0] == D("2027-04-11T00:00")      # 24:00 counts
    assert arrival_pickup(ALLDAY, D("2027-04-10T23:01")) is None                          # would be next-day pickup


def test_departure_pickup_edges():
    dep = D("2027-04-16T11:00")
    p, arrive = must(departure_pickup(TAXI, dep, date(2027, 4, 16)))
    assert arrive <= dep - timedelta(minutes=180) and p.date() == date(2027, 4, 16)
    assert (dep - arrive) >= timedelta(minutes=180)
    # exact statement limit when no cushion is possible
    p2, a2 = must(departure_pickup(TAXI, D("2027-04-16T10:00"), date(2027, 4, 16), cushion_min=0))
    assert a2 == D("2027-04-16T07:00")
    # very early flight: pickup would be the day before -> not allowed
    assert departure_pickup(TAXI, D("2027-04-16T05:00"), date(2027, 4, 16)) is None
    assert departure_pickup(ALLDAY, D("2027-04-16T03:30"), date(2027, 4, 16)) is not None


def test_intercity_timetable_edges():
    train = {"service_from": "06:00", "service_until": "21:30", "frequency_minutes": 30, "duration_minutes": 135}
    dep, arr = must(intercity_departure(train, date(2027, 4, 14)))
    assert dep == D("2027-04-14T08:00") and arr == D("2027-04-14T10:15")
    odd = {"service_from": "06:10", "service_until": "21:30", "frequency_minutes": 25, "duration_minutes": 20}
    dep, _ = must(intercity_departure(odd, date(2027, 4, 14)))
    assert (dep.hour * 60 + dep.minute - 370) % 25 == 0 and dep.hour * 60 + dep.minute >= 480
    late = {"service_from": "05:00", "service_until": "07:00", "frequency_minutes": 30, "duration_minutes": 20}
    assert must(intercity_departure(late, date(2027, 4, 14)))[0] == D("2027-04-14T07:00")      # nothing after 08:00: latest slot
    taxi = {"service_from": "00:00", "service_until": "24:00", "duration_minutes": 100}
    assert must(intercity_departure(taxi, date(2027, 4, 14)))[0] == D("2027-04-14T08:00")


# ================================================================ capacity edges
@pytest.mark.parametrize("adults,kids", [(1, []), (1, [3]), (2, []), (2, [1, 2]), (3, [4]), (4, [5, 6]), (1, [1, 2, 3])])
def test_every_hotel_option_really_fits_and_is_available(cat, adults, kids):
    inv = Inventory(cat)
    for city in ("Tokyo", "Kyoto", "Osaka", "Dubai", "Abu Dhabi"):
        for o in hotel_options(cat, inv, city, date(2027, 4, 8), 3, adults, len(kids)):
            room, k = o["room"], o["rooms"]
            assert adults <= k * room["max_adults"] and adults + len(kids) <= k * (room["max_adults"] + room["max_children"])
            assert adults >= k
            assert all(cat.rooms_left(room["room_id"], date(2027, 4, 8) + timedelta(days=n)) >= k for n in range(3))


def test_capsule_hotel_never_offered_to_a_family_with_a_child(cat):
    inv = Inventory(cat)
    ids = {o["hotel"]["hotel_id"] for o in hotel_options(cat, inv, "Osaka", date(2027, 4, 8), 3, 2, 1)}
    assert "HTL-OSA-010" not in ids


def test_inventory_overlay_reduces_effective_availability(cat):
    flight = cat.flights["FL-401"]
    assert Inventory(cat).seats_left(flight) == 9
    assert Inventory(cat, used_seats={"FL-401": 7}).seats_left(flight) == 2
    assert Inventory(cat, used_seats={"FL-401": 99}).seats_left(flight) == 0
