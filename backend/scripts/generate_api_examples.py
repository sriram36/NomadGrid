"""Generate docs/api-examples/*.json by calling the REAL API (so the examples can never drift from the code).

Run from the backend folder:  python scripts/generate_api_examples.py
"""
import json
import sys
import tempfile
import warnings
from datetime import date
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient   # noqa: E402

from app.api.app import create_app           # noqa: E402
from app.engine.attractions import is_open_on  # noqa: E402

OUT = Path(__file__).resolve().parents[2] / "docs" / "api-examples"
OUT.mkdir(parents=True, exist_ok=True)
client = TestClient(create_app(db_path=Path(tempfile.mkdtemp()) / "examples.sqlite"))
cat = client.app.state.cat
MENON = {"departure_city": "Bengaluru", "country": "Japan", "start_date": "2027-04-10", "nights": 6,
         "adults": 2, "child_ages": [6], "budget_inr": 350000}


def save(name, status, body):
    (OUT / f"{name}.json").write_text(
        json.dumps({"_http_status": status, "body": body}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  {name}.json  ({status})")


def get(path, **params):
    r = client.get(path, params=params)
    return r.status_code, r.json()


def post(path, body=None):
    r = client.post(path, json=body)
    return r.status_code, r.json()


# ---- meta + build outcomes
save("meta", *get("/api/meta"))
s, j = post("/api/packages", MENON)
save("build_package_menon", s, j)
pkg = j["package"]
pid, last_city = pkg["package_id"], pkg["city_plan"][-1]["city"]
save("build_over_budget", *post("/api/packages", {**MENON, "budget_inr": 200000}))
save("build_no_package_out_of_window", *post("/api/packages", {**MENON, "start_date": "2027-04-19", "nights": 5}))
save("build_no_package_too_many_travelers", *post("/api/packages", {**MENON, "adults": 6, "child_ages": [3, 4, 5, 6, 7, 8]}))
save("build_validation_error", *post("/api/packages", {**MENON, "nights": 2, "adults": 0, "child_ages": [18], "budget_inr": -5}))

# ---- options (with price differences)
save("options_hotels", *get(f"/api/packages/{pid}/options/hotels", city=last_city))
save("options_flights_arrival", *get(f"/api/packages/{pid}/options/flights", leg="ARRIVAL"))
save("options_flights_return", *get(f"/api/packages/{pid}/options/flights", leg="RETURN"))
full_day = next(d["date"] for d in pkg["days"] if d["kind"] == "FULL")
save("options_attractions", *get(f"/api/packages/{pid}/options/attractions", date=full_day))

# ---- changes: applied, refused, budget exceeded
hotels = client.get(f"/api/packages/{pid}/options/hotels", params={"city": last_city}).json()["options"]
cheaper = next(o for o in hotels if o["available"] and not o["current"] and o["price_delta_inr"] < 0)
save("change_hotel_applied", *post(f"/api/packages/{pid}/changes", {
    "op": "CHANGE_HOTEL", "city": last_city, "hotel_id": cheaper["hotel_id"], "room_id": cheaper["room_id"]}))
save("change_hotel_refused_room_does_not_fit", *post(f"/api/packages/{pid}/changes", {
    "op": "CHANGE_HOTEL", "city": "Osaka", "hotel_id": "HTL-OSA-010", "room_id": "RM-OSA-010-A"}))
save("change_flight_refused_wrong_airport", *post(f"/api/packages/{pid}/changes", {
    "op": "CHANGE_FLIGHT", "leg": "ARRIVAL", "flight_id": "FL-403"}))
closed = next(((a, d["date"]) for d in pkg["days"] if d["kind"] != "LAST" for a in cat.attractions_in(d["city"])
               if not is_open_on(a, date.fromisoformat(d["date"]))), None)
if closed:
    save("change_attraction_refused_closed", *post(f"/api/packages/{pid}/changes", {
        "op": "ADD_ATTRACTION", "attraction_id": closed[0]["attraction_id"], "date": closed[1]}))
opts = client.get(f"/api/packages/{pid}/options/attractions", params={"date": full_day}).json()["options"]
save("change_attraction_added", *post(f"/api/packages/{pid}/changes", {
    "op": "ADD_ATTRACTION", "attraction_id": opts[0]["attraction_id"], "date": full_day,
    "start": opts[0]["start_choices"][0], "raise_budget": True}))
cheapest = client.post("/api/packages", json={**MENON, "budget_inr": 1}).json()["cheapest_total_inr"]
tight = client.post("/api/packages", json={**MENON, "budget_inr": cheapest + 2000}).json()["package"]
tid, tlast = tight["package_id"], tight["city_plan"][-1]["city"]
pricey = next(o for o in client.get(f"/api/packages/{tid}/options/hotels", params={"city": tlast}).json()["options"]
              if o["available"] and not o["fits_budget"])
body = {"op": "CHANGE_HOTEL", "city": tlast, "hotel_id": pricey["hotel_id"], "room_id": pricey["room_id"]}
save("change_budget_exceeded", *post(f"/api/packages/{tid}/changes", body))
save("change_budget_raised_and_applied", *post(f"/api/packages/{tid}/changes", {**body, "raise_budget": True}))

# ---- confirm, lookup, export
save("export_trip_format_planned", 200, client.get(f"/api/packages/{pid}/export").json())
s, c = post(f"/api/packages/{pid}/confirm")
save("confirm", s, c)
save("reservation_lookup", *get(f"/api/reservations/{c['reservation_number']}"))
save("reservation_not_found", *get("/api/reservations/0000000000"))
save("package_not_found", *get("/api/packages/pkg_doesnotexist"))
save("change_refused_package_locked", *post(f"/api/packages/{pid}/changes", {"op": "REMOVE_ATTRACTION", "item_id": "i1"}))
save("export_trip_format_booked", 200, client.get(f"/api/packages/{pid}/export").json())
print("done")
