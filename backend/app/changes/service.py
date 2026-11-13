"""Apply one change to a stored package and list the options for a change (with price differences).

Every change: rebuild an editable itinerary from the stored package -> apply the edit (ops.py) -> recompute
dependent parts -> re-run the independent validator -> check the budget. The result is APPLIED, REFUSED
(a hard rule would break), BUDGET_EXCEEDED (legal but over budget; needs the traveler's consent) or
PINNED_CONFLICT (the traveler decides). Anything the traveler picked is `pinned` and never dropped silently.
"""
from dataclasses import replace
from datetime import date, datetime
from typing import List

from app.changes.refusal import Refusal
from app.changes.ops import OPS, free_start_choices
from app.changes.rebuild import parse_date, recompute_metrics, itinerary_from_package, night_city
from app.core.pricing import attraction_price, flight_price, hotel_price, rooms_needed
from app.engine import attractions as attr
from app.engine.alternatives import inr
from app.engine.models import Itinerary
from app.export.package import time_label, to_package, to_trip_format
from app.validator.validate import validate_trip


# ============================================================================ apply
def _sig(item: dict):
    return (item["type"], item["catalog_id"], item["start"], item["end"], item["price_inr"], item["quantity"],
            item.get("room_id"))


def _summary(op: dict, it: Itinerary, delta: int, total: int) -> str:
    kind = op["op"]
    money = f"Total is now ₹{inr(total)} ({'+' if delta >= 0 else '−'}₹{inr(abs(delta))})."
    if kind == "CHANGE_HOTEL":
        leg = next(l for l in it.legs if l.city == op["city"])
        return f"Hotel in {leg.city} changed to {leg.hotel['name']} ({leg.room['name']}). {money}"
    if kind == "CHANGE_FLIGHT":
        f = it.arr_flight if op["leg"] == "ARRIVAL" else it.ret_flight
        return f"{op['leg'].title()} flight changed to {f['airline']} {f['flight_number']}. {money}"
    if kind == "ADD_ATTRACTION":
        v = next(v for v in it.visits if v.attraction["attraction_id"] == op["attraction_id"])
        return f"Added {v.attraction['name']} on {v.day:%a %d %b} at {time_label(v.start)}. {money}"
    if kind == "CHANGE_CITY_PLAN":
        plan = " → ".join(f"{l.city} ({l.nights} nights)" for l in it.legs)
        return f"City plan changed to {plan}. {money}"
    return f"Attraction removed. {money}"


def _knock_on(old_items: List[dict], new_items: List[dict]) -> List[str]:
    """G1: plain sentences about OTHER bookings that moved because of this change."""
    labels = {"AIRPORT_ARRIVAL": "Your airport pickup on arrival", "AIRPORT_DEPARTURE": "Your pickup for the flight home"}
    old = {i.get("leg"): i for i in old_items if i["type"] == "transfer"}
    new = {i.get("leg"): i for i in new_items if i["type"] == "transfer"}
    out = []
    for leg, label in labels.items():
        a, b = old.get(leg), new.get(leg)
        if a and b and (a["start"] != b["start"] or a["catalog_id"] != b["catalog_id"]):
            out.append(f"{label} moves from {time_label(datetime.fromisoformat(a['start']))} to "
                       f"{time_label(datetime.fromisoformat(b['start']))}"
                       + (f" ({b['name']})." if a["catalog_id"] != b["catalog_id"] else "."))
    return out


def apply_change(pkg: dict, op: dict, cat, inv, with_cheaper: bool = True) -> dict:
    """Apply one change to a stored package (never persists; the caller saves on APPLIED)."""
    if pkg.get("status") == "BOOKED":
        return Refusal("PACKAGE_LOCKED", "This holiday is already booked, so it can't be changed.").to_response()
    handler = OPS.get(op.get("op", "")) if isinstance(op, dict) else None
    if handler is None:
        return Refusal("UNKNOWN_OP", "Unknown change. Use CHANGE_HOTEL, CHANGE_FLIGHT, ADD_ATTRACTION, "
                                     "REMOVE_ATTRACTION or CHANGE_CITY_PLAN.").to_response()
    it = itinerary_from_package(pkg, cat)
    try:
        extra_warnings = handler(it, op, cat, inv)
    except Refusal as r:
        return r.to_response("PINNED_CONFLICT" if r.code == "PINNED_CONFLICT" else "REFUSED")
    recompute_metrics(it)
    old_total, budget = pkg["pricing"]["total_inr"], pkg["pricing"]["budget_inr"]
    new_pkg = to_package(it, cat, pkg["package_id"], pkg["traveler"], variant=pkg.get("variant", "DEFAULT"))
    new_total = new_pkg["pricing"]["total_inr"]
    if new_total > budget and new_total > old_total:
        if op.get("raise_budget") is True:
            it.request = replace(it.request, budget_inr=new_total)
            new_pkg = to_package(it, cat, pkg["package_id"], pkg["traveler"], variant=pkg.get("variant", "DEFAULT"))
            extra_warnings = extra_warnings + [f"BUDGET_RAISED: your budget is now ₹{inr(new_total)}."]
        else:
            out = {"result": "BUDGET_EXCEEDED", "new_total_inr": new_total, "over_by_inr": new_total - budget,
                   "message": f"This change would take your total to ₹{inr(new_total)}, which is ₹{inr(new_total - budget)} "
                              f"over your ₹{inr(budget)} budget.",
                   "suggestion": "Pick a cheaper option, or raise your budget to apply it.",
                   "raise_budget_to_inr": new_total}
            if with_cheaper and op["op"] in ("CHANGE_HOTEL", "CHANGE_FLIGHT"):
                out["cheaper_options"] = _cheaper_options(pkg, op, cat, inv)
            return out
    violations = validate_trip(to_trip_format(new_pkg), cat)
    if violations:
        v0 = violations[0]
        return {"result": "REFUSED", "reason_code": "VALIDATION_FAILED",
                "reason": f"That change would break a travel rule: {v0.message}",
                "violations": [v.to_dict() for v in violations]}
    old_sigs = {_sig(i) for i in pkg["items"]}
    changed = [i["item_id"] for i in new_pkg["items"] if _sig(i) not in old_sigs]
    delta = new_total - old_total
    return {"result": "APPLIED", "package": new_pkg, "price_delta_inr": delta,
            "warnings": extra_warnings + new_pkg["warnings"], "changed_item_ids": changed,
            "knock_on": _knock_on(pkg["items"], new_pkg["items"]),
            "summary": _summary(op, it, delta, new_total)}


def _cheaper_options(pkg: dict, op: dict, cat, inv, limit: int = 5) -> list:
    base = {"hotel": lambda: hotel_options_for(pkg, op["city"], cat, inv, _nested=True),
            "flight": lambda: flight_options_for(pkg, op["leg"], cat, inv, _nested=True)}
    opts = base["hotel" if op["op"] == "CHANGE_HOTEL" else "flight"]()
    fits = [o for o in opts if o["available"] and o["fits_budget"] and not o["current"]]
    fits.sort(key=lambda o: o["price_delta_inr"])
    return fits[:limit]


# ============================================================================ options (with price differences)
def _status(res: dict) -> dict:
    if res["result"] == "APPLIED":
        return {"available": True, "fits_budget": True, "budget_needed_inr": 0, "price_delta_inr": res["price_delta_inr"],
                "reason_unavailable": None, "reason_code": None}
    if res["result"] == "BUDGET_EXCEEDED":
        return {"available": True, "fits_budget": False, "budget_needed_inr": res["over_by_inr"],
                "price_delta_inr": res["new_total_inr"] - 0, "reason_unavailable": None, "reason_code": None,
                "_new_total": res["new_total_inr"]}
    return {"available": False, "fits_budget": False, "budget_needed_inr": 0, "price_delta_inr": None,
            "reason_unavailable": res.get("reason"), "reason_code": res.get("reason_code")}


def hotel_options_for(pkg: dict, city: str, cat, inv, _nested: bool = False) -> List[dict]:
    req = pkg["request"]
    adults, children = req["adults"], len(req["child_ages"])
    leg = next((l for l in pkg["city_plan"] if l["city"] == city), None)
    if leg is None:
        return []
    cur = next(i for i in pkg["items"] if i["type"] == "hotel" and i["city"] == city)
    old_total = pkg["pricing"]["total_inr"]
    out = []
    for hotel in cat.hotels_in(city):
        for room in cat.rooms_of(hotel["hotel_id"]):
            k = rooms_needed(room, adults, children)
            if k is None:
                continue                      # can never hold this party: not an option
            res = apply_change(pkg, {"op": "CHANGE_HOTEL", "city": city, "hotel_id": hotel["hotel_id"],
                                     "room_id": room["room_id"]}, cat, inv, with_cheaper=False)
            st = _status(res)
            if st["available"] and "_new_total" in st:
                st["price_delta_inr"] = st.pop("_new_total") - old_total
            out.append({"hotel_id": hotel["hotel_id"], "room_id": room["room_id"], "name": hotel["name"],
                        "stars": hotel["stars"], "rating": hotel["rating"], "area": hotel["area"],
                        "room_type": room["room_type"], "room_name": room["name"], "rooms_needed": k,
                        "price_inr": hotel_price(room, k, leg["nights"]), "family_friendly": hotel["family_friendly"],
                        "image": ("/" + hotel["image"]) if hotel.get("image") else None,
                        "current": hotel["hotel_id"] == cur["catalog_id"] and room["room_id"] == cur["room_id"], **st})
    out.sort(key=lambda o: (not o["current"], o["price_inr"], o["hotel_id"]))
    return out


def flight_options_for(pkg: dict, leg: str, cat, inv, _nested: bool = False) -> List[dict]:
    r = pkg["request"]
    start, end = date.fromisoformat(r["start_date"]), date.fromisoformat(pkg["end_date"])
    dep, code = cat.departure_airport(r["departure_city"]), cat.country_code(r["country"])
    flights = cat.arrivals(dep, code, start) if leg == "ARRIVAL" else cat.returns(dep, code, end)
    cur = next(i for i in pkg["items"] if i["type"] == "flight" and i.get("leg") == leg)
    old_total = pkg["pricing"]["total_inr"]
    travelers = r["adults"] + len(r["child_ages"])
    out = []
    for f in flights:
        res = apply_change(pkg, {"op": "CHANGE_FLIGHT", "leg": leg, "flight_id": f["flight_id"]}, cat, inv,
                           with_cheaper=False)
        st = _status(res)
        if st["available"] and "_new_total" in st:
            st["price_delta_inr"] = st.pop("_new_total") - old_total
        out.append({"flight_id": f["flight_id"], "airline": f["airline"], "flight_number": f["flight_number"],
                    "from": f["from"], "to": f["to"], "departure": f["departure_local"][:16],
                    "arrival": f["arrival_local"][:16], "stops": f["stops"], "duration_minutes": f["duration_minutes"],
                    "price_inr": flight_price(f, travelers), "seats_left": inv.seats_left(f),
                    "current": f["flight_id"] == cur["catalog_id"], **st})
    out.sort(key=lambda o: (not o["current"], o["price_inr"], o["flight_id"]))
    return out


def attraction_options_for(pkg: dict, day_text: str, cat, inv) -> dict:
    day = parse_date(day_text)
    it = itinerary_from_package(pkg, cat)
    req = it.request
    if day is None or not (req.start_date <= day < req.end_date):
        return {"error": "INVALID_DAY", "options": []}
    city = night_city(it, day)
    used = {v.attraction["attraction_id"] for v in it.visits}
    total, budget = pkg["pricing"]["total_inr"], pkg["pricing"]["budget_inr"]
    out = []
    for a in cat.attractions_in(city):
        if a["attraction_id"] in used or not attr.is_open_on(a, day):
            continue
        choices = free_start_choices(it, a, day)
        if not choices:
            continue
        price = attraction_price(a, req.adults, req.children)
        out.append({"attraction_id": a["attraction_id"], "name": a["name"], "category": a["category"],
                    "duration_minutes": a["visit_minutes"], "price_inr": price, "price_delta_inr": price,
                    "child_friendly": a.get("child_friendly", False), "image": ("/" + a["image"]) if a.get("image") else None,
                    "start_choices": [f"{s // 60:02d}:{s % 60:02d}" for s in choices[:16]],
                    "available": True, "fits_budget": total + price <= budget,
                    "budget_needed_inr": max(0, total + price - budget)})
    out.sort(key=lambda o: (o["price_inr"], o["attraction_id"]))
    return {"date": day.isoformat(), "city": city, "options": out}
