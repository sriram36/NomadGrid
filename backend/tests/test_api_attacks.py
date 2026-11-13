"""Try to break the API: hostile input, impossible trips, budget edges, confirm races, tampering."""
import copy
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from app.api.app import create_app
from app.export.package import to_trip_format
from app.validator.validate import validate_trip
from tests.conftest import MENON


def post(client, **over):
    body = copy.deepcopy(MENON)
    body.update(over)
    for k in [k for k, v in over.items() if v == "__DELETE__"]:
        body.pop(k)
    return client.post("/api/packages", json=body)


def fields(resp):
    return {f["field"] for f in resp.json()["error"]["fields"]}


# ============================================================ M1: invalid values -> clear 422
BAD = [
    ("departure_city", "Atlantis"), ("departure_city", None), ("departure_city", 123), ("departure_city", ""),
    ("departure_city", "bengaluru"), ("departure_city", "Bengaluru "),
    ("country", "Narnia"), ("country", None), ("country", "japan"), ("country", ["Japan"]),
    ("start_date", "2027-02-30"), ("start_date", "10/04/2027"), ("start_date", ""), ("start_date", 20270410),
    ("start_date", None), ("start_date", "2027-4-10"), ("start_date", "2027-04-10T00:00"),
    ("nights", 2), ("nights", 11), ("nights", 0), ("nights", -1), ("nights", 6.5), ("nights", "6"),
    ("nights", True), ("nights", None), ("nights", 10 ** 12),
    ("adults", 0), ("adults", -1), ("adults", 21), ("adults", 2.5), ("adults", "2"), ("adults", None),
    ("adults", True), ("adults", 10 ** 9),
    ("child_ages", [18]), ("child_ages", [-1]), ("child_ages", [6.5]), ("child_ages", ["six"]),
    ("child_ages", "6"), ("child_ages", [6] * 21), ("child_ages", None), ("child_ages", [True]),
    ("child_ages", [[6]]), ("child_ages", [200]),
    ("budget_inr", 0), ("budget_inr", -5), ("budget_inr", 10 ** 12), ("budget_inr", "350000"),
    ("budget_inr", None), ("budget_inr", True), ("budget_inr", 350000.5), ("budget_inr", [350000]),
    ("traveler_name", "x" * 61), ("traveler_name", 5),
]


@pytest.mark.parametrize("field,value", BAD)
def test_invalid_value_gets_a_clear_message_for_that_field(client, field, value):
    r = post(client, **{field: value})
    assert r.status_code == 422, (field, value, r.text[:200])
    assert field in fields(r)
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
    msg = next(f["message"] for f in r.json()["error"]["fields"] if f["field"] == field)
    assert len(msg) > 10 and "Traceback" not in msg


@pytest.mark.parametrize("body", [{}, [], "text", 5, None, [1, 2], {"nights": 6}])
def test_garbage_bodies_never_crash(client, body):
    r = client.post("/api/packages", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"


def test_non_json_body_is_a_clean_422(client):
    r = client.post("/api/packages", content=b"{not json", headers={"content-type": "application/json"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "VALIDATION_ERROR"
    r = client.post("/api/packages", content=b"", headers={"content-type": "application/json"})
    assert r.status_code == 422


def test_all_errors_reported_together(client):
    r = client.post("/api/packages", json={})
    assert {"departure_city", "country", "start_date", "nights", "adults", "budget_inr"} <= fields(r)


def test_valid_oddities_are_accepted(client):
    assert post(client, budget_inr=350000.0).json()["outcome"] in ("PACKAGE", "OVER_BUDGET")
    assert post(client, child_ages="__DELETE__").status_code == 200    # missing child_ages = no children
    assert post(client, traveler_name="Robert'); DROP TABLE packages;--").json()["outcome"] == "PACKAGE"
    assert post(client, traveler_name="<script>alert(1)</script>").status_code == 200


# ============================================================ M2: impossible requests say why
@pytest.mark.parametrize("start,nights", [("2027-03-30", 3), ("2027-03-31", 5), ("2027-04-19", 3), ("2027-04-18", 3),
                                          ("2030-01-01", 5), ("1999-04-10", 5), ("2027-04-20", 3)])
def test_outside_the_data_window_has_no_package_and_says_so(client, start, nights):
    j = post(client, start_date=start, nights=nights).json()
    assert j["outcome"] == "NO_PACKAGE" and j["reason_code"] == "OUT_OF_WINDOW"
    assert "1 to 20 April 2027" in j["message"]


def test_window_boundaries_do_not_crash(client):
    for start, n in [("2027-04-01", 3), ("2027-04-17", 3), ("2027-04-10", 10), ("2027-04-01", 10)]:
        j = post(client, start_date=start, nights=n).json()
        assert j["outcome"] in ("PACKAGE", "NO_PACKAGE", "OVER_BUDGET")


def test_too_many_travelers_has_no_package_and_names_the_seats(client):
    j = post(client, adults=6, child_ages=[3, 4, 5, 6, 7, 8]).json()
    assert j["outcome"] == "NO_PACKAGE"
    assert j["reason_code"] in ("INSUFFICIENT_SEATS_ARRIVAL", "NO_ARRIVAL_FLIGHT")
    assert "12" in j["message"] or "seat" in j["message"].lower() or "flight" in j["message"].lower()


def test_no_flights_that_day_says_so(client):
    j = post(client, departure_city="Delhi", start_date="2027-04-09", nights=4).json()
    assert j["outcome"] in ("NO_PACKAGE", "PACKAGE", "OVER_BUDGET")
    if j["outcome"] == "NO_PACKAGE":
        assert j["message"]


def test_three_nights_never_gets_two_cities(client):
    for dep in ("Bengaluru", "Delhi", "Mumbai", "Chennai"):
        for country in ("Japan", "United Arab Emirates"):
            j = post(client, departure_city=dep, country=country, nights=3, start_date="2027-04-05").json()
            if j["outcome"] == "PACKAGE":
                assert len(j["package"]["city_plan"]) == 1


# ============================================================ budget is the first constraint
def test_budget_edges_are_exact(client):
    j = post(client, budget_inr=1).json()
    assert j["outcome"] == "OVER_BUDGET"
    cheapest = j["cheapest_total_inr"]
    assert cheapest > 1 and j["over_by_inr"] == cheapest - 1
    assert "not possible" in j["message"] and "₹" in j["message"]
    ok = post(client, budget_inr=cheapest).json()
    assert ok["outcome"] == "PACKAGE" and ok["package"]["pricing"]["total_inr"] == cheapest
    over = post(client, budget_inr=cheapest - 1).json()
    assert over["outcome"] == "OVER_BUDGET" and over["cheapest_total_inr"] == cheapest


def test_a_package_is_never_over_budget(client):
    for b in (150000, 200000, 250000, 300000, 350000, 400000, 500000, 800000, 2000000):
        j = post(client, budget_inr=b).json()
        if j["outcome"] == "PACKAGE":
            assert j["package"]["pricing"]["total_inr"] <= b


def test_bigger_budget_gets_a_better_package_near_that_budget(client):
    small = post(client, budget_inr=260000).json()
    big = post(client, budget_inr=450000).json()
    assert small["outcome"] == big["outcome"] == "PACKAGE"
    s, b = small["package"], big["package"]
    assert b["pricing"]["total_inr"] > s["pricing"]["total_inr"]
    assert b["metrics"]["avg_hotel_stars"] >= s["metrics"]["avg_hotel_stars"]
    assert b["pricing"]["total_inr"] >= 0.7 * 450000       # uses the budget, not just 2 lakh


def test_over_budget_alternatives_are_valid_packages_within_budget(client, cat):
    j = post(client, budget_inr=200000).json()
    assert j["outcome"] == "OVER_BUDGET"
    assert j["raise_budget"]["budget_inr"] == j["cheapest_total_inr"]
    for alt in j["alternatives"]:
        pkg = client.get(f"/api/packages/{alt['package_id']}").json()
        assert validate_trip(to_trip_format(pkg), cat) == []
        assert pkg["pricing"]["total_inr"] <= 200000
        assert alt["total_inr"] == pkg["pricing"]["total_inr"] and alt["levers"] and alt["label"]


def test_raising_the_budget_builds_the_original_request(client):
    j = post(client, budget_inr=200000).json()
    again = post(client, budget_inr=j["raise_budget"]["budget_inr"]).json()
    assert again["outcome"] == "PACKAGE"


def test_deterministic_same_request_same_package(client):
    a = post(client).json()["package"]
    b = post(client).json()["package"]
    key = lambda p: [(i["type"], i["catalog_id"], i["start"], i["price_inr"]) for i in p["items"]]
    assert key(a) == key(b)


# ============================================================ other countries / cities
@pytest.mark.parametrize("dep", ["Bengaluru", "Delhi", "Mumbai", "Chennai"])
@pytest.mark.parametrize("country", ["Japan", "United Arab Emirates"])
def test_every_departure_and_country_combination_builds_valid_packages(client, cat, dep, country):
    built = 0
    for start, n in [("2027-04-04", 4), ("2027-04-08", 6), ("2027-04-10", 8)]:
        j = post(client, departure_city=dep, country=country, start_date=start, nights=n, budget_inr=600000).json()
        if j["outcome"] == "PACKAGE":
            built += 1
            assert validate_trip(to_trip_format(j["package"]), cat, first_package=True) == []
    assert built >= 1, f"no package at all for {dep} -> {country}"


# ============================================================ meta, lookup and 404s
def test_meta_feeds_the_form(client):
    m = client.get("/api/meta").json()
    assert {d["city"] for d in m["departure_cities"]} == {"Bengaluru", "Delhi", "Mumbai", "Chennai"}
    assert {c["name"] for c in m["countries"]} == {"Japan", "United Arab Emirates"}
    assert m["rules"]["min_nights"] == 3 and m["rules"]["max_nights"] == 10


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize("number", ["1", "123", "123456789", "12345678901", "abcdefghij", "0000000000",
                                    "1234567890", "12345 67890", "１２３４５６７８９０", "-123456789", "1e9999999",
                                    "%27%20OR%201=1", "..%2F..%2Fetc", "9" * 200])
def test_wrong_reservation_numbers_show_not_found(client, number):
    r = client.get(f"/api/reservations/{number}")
    assert r.status_code == 404, number
    assert r.json()["error"]["code"] == "RESERVATION_NOT_FOUND" and "not found" in r.json()["error"]["message"].lower()


@pytest.mark.parametrize("path", ["/api/packages/nope", "/api/packages/' OR 1=1 --", "/api/packages/..%2F..%2Fx",
                                  "/api/packages/nope/export", "/api/packages/nope/options/hotels?city=Tokyo",
                                  "/api/packages/nope/options/flights?leg=ARRIVAL"])
def test_unknown_package_is_a_clean_404(client, path):
    r = client.get(path)
    assert r.status_code == 404 and r.json()["error"]["code"] in ("PACKAGE_NOT_FOUND", "NOT_FOUND")


def test_confirming_or_changing_an_unknown_package_is_404(client):
    assert client.post("/api/packages/nope/confirm").status_code == 404
    assert client.post("/api/packages/nope/changes", json={"op": "CHANGE_HOTEL"}).status_code == 404


# ============================================================ M7: confirm, restart, export
def build_menon(client):
    return client.post("/api/packages", json=MENON).json()["package"]


def test_confirm_gives_unique_10_digit_number_and_is_idempotent(client):
    pkg = build_menon(client)
    n1 = client.post(f"/api/packages/{pkg['package_id']}/confirm").json()["reservation_number"]
    n2 = client.post(f"/api/packages/{pkg['package_id']}/confirm").json()["reservation_number"]
    assert n1 == n2 and len(n1) == 10 and n1.isdigit() and n1[0] != "0"
    other = build_menon(client)
    n3 = client.post(f"/api/packages/{other['package_id']}/confirm").json()["reservation_number"]
    assert n3 != n1


def test_reservation_survives_backend_restart(db_path):
    c1 = TestClient(create_app(db_path=db_path))
    pkg = build_menon(c1)
    num = c1.post(f"/api/packages/{pkg['package_id']}/confirm").json()["reservation_number"]
    c2 = TestClient(create_app(db_path=db_path))                 # a brand new app on the same database
    got = c2.get(f"/api/reservations/{num}").json()
    assert got["status"] == "BOOKED" and got["reservation"]["number"] == num
    assert c2.get(f"/api/packages/{pkg['package_id']}").json()["status"] == "BOOKED"
    assert all(i["status"] == "BOOKED" and i["booking"] == {"reference": num} for i in got["items"])


def test_unconfirmed_package_survives_restart_too(db_path):
    c1 = TestClient(create_app(db_path=db_path))
    pkg = build_menon(c1)
    c2 = TestClient(create_app(db_path=db_path))
    assert c2.get(f"/api/packages/{pkg['package_id']}").json()["pricing"] == pkg["pricing"]


def test_export_is_valid_and_booked_export_carries_the_reference(client, cat):
    pkg = build_menon(client)
    r = client.get(f"/api/packages/{pkg['package_id']}/export")
    assert "attachment" in r.headers["content-disposition"]
    t = r.json()
    assert t["status"] == "PLANNED" and t["country"] == "Japan" and t["items"][0]["booking"] is None
    assert validate_trip(t, cat) == []
    num = client.post(f"/api/packages/{pkg['package_id']}/confirm").json()["reservation_number"]
    t2 = client.get(f"/api/packages/{pkg['package_id']}/export").json()
    assert t2["status"] == "BOOKED" and all(i["booking"]["reference"] == num and isinstance(i["booking"]["reference"], str)
                                            for i in t2["items"])
    assert validate_trip(t2, cat) == []


def test_concurrent_confirms_of_one_package_give_one_number(client):
    pkg = build_menon(client)
    store = client.app.state.store

    def make_booked(p, number, when):
        return dict(p, status="BOOKED", reservation={"number": number, "confirmed_at": when})

    with ThreadPoolExecutor(12) as pool:
        numbers = list(pool.map(lambda _: store.confirm(pkg["package_id"], make_booked)[0], range(24)))
    assert len(set(numbers)) == 1


def test_many_confirms_all_get_distinct_numbers(client):
    store, nums = client.app.state.store, set()
    base = build_menon(client)
    for i in range(60):
        p = dict(base, package_id=f"pkg_bulk{i}")
        store.save_package(p)
        nums.add(store.confirm(p["package_id"], lambda q, n, w: dict(q, status="BOOKED",
                                                                  reservation={"number": n, "confirmed_at": w}))[0])
    assert len(nums) == 60 and all(len(n) == 10 and n[0] != "0" for n in nums)


def test_corrupt_database_row_is_a_clean_500_not_a_stack_trace(db_path):
    c = TestClient(create_app(db_path=db_path), raise_server_exceptions=False)
    pkg = build_menon(c)
    with sqlite3.connect(db_path) as con:
        con.execute("UPDATE packages SET package_json='{broken' WHERE id=?", (pkg["package_id"],))
    r = c.get(f"/api/packages/{pkg['package_id']}")
    assert r.status_code == 500 and r.json()["error"]["code"] == "INTERNAL_ERROR"
    assert "Traceback" not in r.text and "json" not in r.text.lower()


def test_data_files_are_never_modified():
    from app.catalog.loader import data_fingerprint
    from app.config import DATA_DIR
    before = data_fingerprint(DATA_DIR)
    c = TestClient(create_app(db_path=__import__("tempfile").mkdtemp() + "/x.sqlite"))
    c.post("/api/packages", json=MENON)
    assert data_fingerprint(DATA_DIR) == before
