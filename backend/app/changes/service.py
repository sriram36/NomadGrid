"""M6: change a package (hotel, flight, add/remove attractions) and list the options.

Every change: rebuild an editable itinerary from the stored package -> apply the edit -> recompute
dependent parts (airport transfers, arrival-day visits) -> re-run the independent validator ->
check the budget. The result is APPLIED, REFUSED (a hard rule would break), BUDGET_EXCEEDED
(legal but over budget; needs the traveler's consent) or PINNED_CONFLICT (the traveler decides).

User choices take priority: anything the traveler picked is `pinned` and never dropped silently.
"""
from dataclasses import replace
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.config import DAY_END_MIN, DAY_START_MIN, SETTLE_MIN, VISIT_GAP_MIN
from app.core.pricing import attraction_price, flight_price, hotel_price, rooms_needed
from app.core.timeutil import at, hm, tod, weekday_code
from app.engine import attractions as attr
from app.engine.airport import arrival_transfer, departure_transfer
from app.engine.alternatives import inr
from app.engine.models import Itinerary, Leg, TransferUse, TripRequest, Visit
from app.export.package import time_label, to_package, to_trip_format
from app.validator.validate import validate_trip


class Refusal(Exception):
    def __init__(self, code: str, reason: str, suggestion: Optional[str] = None, options: Optional[list] = None):
        self.code, self.reason, self.suggestion, self.options = code, reason, suggestion, options

    def to_response(self, result: str = "REFUSED") -> dict:
        out = {"result": result, "reason_code": self.code, "reason": self.reason}
        if self.suggestion:
            out["suggestion"] = self.suggestion
        if self.options is not None:
            out["options"] = self.options
        return out


# ============================================================================ rebuild from a stored package
def itinerary_from_package(pkg: dict, cat) -> Itinerary:
    r = pkg["request"]
    req = TripRequest(r["departure_city"], r["country"], date.fromisoformat(r["start_date"]), r["nights"],
                      r["adults"], tuple(r["child_ages"]), r["budget_inr"], r.get("traveler_name", "Traveler"))
    legs: List[Leg] = []
    links: List[TransferUse] = []
    visits: List[Visit] = []
    arr = ret = arr_t = dep_t = None
    arr_pinned = ret_pinned = False
    visit_by_item: Dict[str, Visit] = {}
    for i in pkg["items"]:
        t, tag = i["type"], i.get("leg")
        if t == "flight":
            rec = cat.flights[i["catalog_id"]]
            if tag == "ARRIVAL":
                arr, arr_pinned = rec, bool(i.get("pinned"))
            else:
                ret, ret_pinned = rec, bool(i.get("pinned"))
        elif t == "transfer":
            rec = cat.transfers[i["catalog_id"]]
            p = datetime.fromisoformat(i["start"])
            use = TransferUse(rec, p, datetime.fromisoformat(i["end"]), i["price_inr"], i["quantity"], p.date(),
                              rec.get("from_city"), rec.get("to_city"))
            if tag == "AIRPORT_ARRIVAL":
                arr_t = use
            elif tag == "AIRPORT_DEPARTURE":
                dep_t = use
            else:
                links.append(use)
        elif t == "hotel":
            ci, co = date.fromisoformat(i["start"]), date.fromisoformat(i["end"])
            legs.append(Leg(i["city"], (co - ci).days, ci, co, cat.hotels[i["catalog_id"]], cat.rooms[i["room_id"]],
                            i["quantity"], i["price_inr"], bool(i.get("pinned"))))
        elif t == "attraction":
            s = datetime.fromisoformat(i["start"])
            v = Visit(cat.attractions[i["catalog_id"]], s, datetime.fromisoformat(i["end"]), i["price_inr"],
                      s.date(), bool(i.get("pinned")))
            visits.append(v)
            visit_by_item[i["item_id"]] = v
    legs.sort(key=lambda l: l.check_in)
    links.sort(key=lambda l: l.pickup)
    it = Itinerary(req, legs, arr, ret, arr_t, dep_t, links, visits, {}, arr_pinned, ret_pinned)
    it.visit_by_item = visit_by_item   # type: ignore[attr-defined]
    return it


def _recompute_metrics(it: Itinerary):
    req = it.request
    stars = sum(l.hotel["stars"] * l.nights for l in it.legs) / req.nights
    it.metrics = {
        "transit_minutes": it.arr_flight["duration_minutes"] + it.ret_flight["duration_minutes"]
        + sum(l.rec["duration_minutes"] for l in it.links),
        "avg_hotel_stars": round(stars, 2), "usable_ground_minutes": None, "quality_score": None,
    }


# ============================================================================ helpers
def night_city(it: Itinerary, day: date) -> Optional[str]:
    for l in it.legs:
        if l.check_in <= day < l.check_out:
            return l.city
    return None


def _ready_min(it: Itinerary, day: date) -> int:
    """Minutes after midnight on `day` when the traveler is in that day's city (0 = from the start)."""
    if day == it.request.start_date:
        arrive = it.arr_transfer.arrive
    else:
        arrive = next((l.arrive for l in it.links if l.day == day), None)
    if arrive is None:
        return 0
    return tod(arrive) if arrive.date() == day else 1440


def _retime_arrival_day(it: Itinerary, allow_remove: bool) -> List[str]:
    """After the arrival moved: shift arrival-day visits that no longer fit; never drop a pinned one silently."""
    day = it.request.start_date
    ready = _ready_min(it, day)
    todays = sorted((v for v in it.visits if v.day == day), key=lambda v: v.start)
    cursor, warnings, conflicts, drop = ready, [], [], []
    for v in todays:
        a = v.attraction
        start = max(tod(v.start), cursor)
        end = start + a["visit_minutes"]
        if start >= 1440 or end > hm(a["open_until"]):
            (conflicts if v.pinned else drop).append(v)
            continue
        if start != tod(v.start):
            v.start, v.end = at(day, start), at(day, end)
            warnings.append(f"ARRIVAL_SHIFTED: {a['name']} now starts at {time_label(v.start)} because you arrive later.")
        cursor = end
    if conflicts and not allow_remove:
        names = ", ".join(v.attraction["name"] for v in conflicts)
        raise Refusal(
            "PINNED_CONFLICT",
            f"With this change you reach your hotel around {time_label(it.arr_transfer.arrive)}, which leaves no "
            f"time for {names} on {day:%d %b}.",
            "Keep your current choice, or apply the change and remove it from the plan.",
            [{"action": "KEEP_CURRENT"},
             {"action": "APPLY_AND_REMOVE", "remove": [v.attraction["name"] for v in conflicts],
              "resend_with": {"remove_pinned_conflicts": True}}])
    for v in conflicts + drop:
        it.visits.remove(v)
        warnings.append(f"ARRIVAL_SHIFTED: {v.attraction['name']} no longer fits on {day:%d %b} and was removed.")
    return warnings


def _parse_date(text) -> Optional[date]:
    try:
        return date.fromisoformat(text)
    except Exception:
        return None


# ============================================================================ operations
def op_change_hotel(it, op, cat, inv) -> List[str]:
    req = it.request
    city = op.get("city")
    leg = next((l for l in it.legs if l.city == city), None)
    if leg is None:
        raise Refusal("INVALID_CITY", f"{city!r} is not one of the cities in this holiday: {', '.join(it.cities)}.")
    hotel, room = cat.hotels.get(op.get("hotel_id")), cat.rooms.get(op.get("room_id"))
    if hotel is None or hotel["city"] != city:
        raise Refusal("HOTEL_NOT_FOUND", f"That hotel is not in {city}.")
    if room is None or room["hotel_id"] != hotel["hotel_id"]:
        raise Refusal("ROOM_NOT_FOUND", f"That room type does not belong to {hotel['name']}.")
    k = rooms_needed(room, req.adults, req.children)
    if k is None:
        raise Refusal("ROOM_DOES_NOT_FIT", f"{room['name']} at {hotel['name']} can't hold {req.adults} adult(s) and "
                                           f"{req.children} child(ren).", "Pick a family room or a larger room type.")
    for n in range(leg.nights):
        d = leg.check_in + timedelta(days=n)
        if inv.rooms_left(room["room_id"], d) < k:
            raise Refusal("ROOMS_UNAVAILABLE", f"{hotel['name']} ({room['name']}) is sold out on {d:%d %b}.",
                          "Choose another room type or hotel.")
    leg.hotel, leg.room, leg.rooms, leg.pinned = hotel, room, k, True
    leg.price = hotel_price(room, k, leg.nights)
    warnings: List[str] = []
    idx = it.legs.index(leg)
    if idx == 0:
        got = arrival_transfer(cat, req, it.arr_flight, city, hotel["area"])
        if got is None:
            raise Refusal("NO_AIRPORT_TRANSFER", f"No airport transfer from {it.arr_flight['to']} serves {hotel['area']} "
                                                 f"at a time that works with your arrival flight.",
                          "Choose a hotel in another area, or another arrival flight.")
        it.arr_transfer = TransferUse(got[0], got[1], got[2], got[3], got[4], req.start_date)
    if idx == len(it.legs) - 1:
        got = departure_transfer(cat, req, it.ret_flight, city, hotel["area"], req.end_date)
        if got is None:
            raise Refusal("NO_AIRPORT_TRANSFER", f"No airport transfer from {hotel['area']} reaches "
                                                 f"{it.ret_flight['from']} 3 hours before your flight.",
                          "Choose a hotel in another area, or another return flight.")
        it.dep_transfer = TransferUse(got[0], got[1], got[2], got[3], got[4], req.end_date)
    if idx == 0:
        warnings += _retime_arrival_day(it, bool(op.get("remove_pinned_conflicts")))
    return warnings


def op_change_flight(it, op, cat, inv) -> List[str]:
    req = it.request
    leg = op.get("leg")
    f = cat.flights.get(op.get("flight_id"))
    if leg not in ("ARRIVAL", "RETURN"):
        raise Refusal("INVALID_LEG", "Choose the ARRIVAL or the RETURN flight to change.")
    if f is None:
        raise Refusal("FLIGHT_NOT_FOUND", "We couldn't find that flight.")
    code, dep = cat.country_code(req.country), cat.departure_airport(req.departure_city)
    warnings: List[str] = []
    if leg == "ARRIVAL":
        if f["from"] != dep or cat.country_of_airport(f["to"]) != code or f["_arr"].date() != req.start_date:
            raise Refusal("FLIGHT_MISMATCH", f"That flight does not fly {req.departure_city} → {req.country} and land "
                                             f"on {req.start_date:%d %b}.")
        if it.cities[0] not in cat.airports[f["to"]].get("serves_cities", []):
            raise Refusal("AIRPORT_MISMATCH", f"{f['to']} does not serve {it.cities[0]}, where your holiday starts.",
                          "Pick a flight into an airport that serves your first city.")
        if inv.seats_left(f) < req.travelers:
            raise Refusal("SEATS_UNAVAILABLE", f"Only {inv.seats_left(f)} seat(s) left on that flight; you need {req.travelers}.")
        it.arr_flight, it.arr_pinned = f, True
        first = it.legs[0]
        got = arrival_transfer(cat, req, f, first.city, first.hotel["area"])
        if got is None:
            raise Refusal("NO_AIRPORT_TRANSFER", f"No transfer from {f['to']} to {first.hotel['name']} can run at least "
                                                 f"60 minutes after that flight lands, inside its service hours.",
                          "Pick an earlier flight or a hotel in another area.")
        it.arr_transfer = TransferUse(got[0], got[1], got[2], got[3], got[4], req.start_date)
        warnings += _retime_arrival_day(it, bool(op.get("remove_pinned_conflicts")))
    else:
        if f["to"] != dep or cat.country_of_airport(f["from"]) != code or f["_dep"].date() != req.end_date:
            raise Refusal("FLIGHT_MISMATCH", f"That flight does not fly {req.country} → {req.departure_city} and leave "
                                             f"on {req.end_date:%d %b}.")
        if it.cities[-1] not in cat.airports[f["from"]].get("serves_cities", []):
            raise Refusal("AIRPORT_MISMATCH", f"{f['from']} does not serve {it.cities[-1]}, where your holiday ends.",
                          "Pick a flight from an airport that serves your last city.")
        if inv.seats_left(f) < req.travelers:
            raise Refusal("SEATS_UNAVAILABLE", f"Only {inv.seats_left(f)} seat(s) left on that flight; you need {req.travelers}.")
        it.ret_flight, it.ret_pinned = f, True
        last = it.legs[-1]
        got = departure_transfer(cat, req, f, last.city, last.hotel["area"], req.end_date)
        if got is None:
            raise Refusal("NO_AIRPORT_TRANSFER", f"No transfer from {last.hotel['name']} can get you to {f['from']} "
                                                 f"3 hours before that flight, inside its service hours.",
                          "Pick a later flight or a hotel in another area.")
        it.dep_transfer = TransferUse(got[0], got[1], got[2], got[3], got[4], req.end_date)
    return warnings


def _free_start_choices(it: Itinerary, a: dict, day: date, step: int = 30) -> List[int]:
    """Start minutes (statement rules only) at which `a` fits on `day` without overlapping other visits."""
    ready = _ready_min(it, day)
    lo, hi = max(hm(a["open_from"]), ready), hm(a["open_until"]) - a["visit_minutes"]
    others = [(tod(v.start), tod(v.end)) for v in it.visits if v.day == day]
    out, s = [], lo
    s = ((s + step - 1) // step) * step if s % step else s
    while s <= hi:
        e = s + a["visit_minutes"]
        if all(e <= os or s >= oe for os, oe in others):
            out.append(s)
        s += step
    return out


def _auto_start(it: Itinerary, a: dict, day: date) -> Optional[int]:
    """Earliest comfortable start (08:30-21:30, 30-min gaps, settling time); else any rule-valid start."""
    ready = _ready_min(it, day)
    lo = max(DAY_START_MIN, hm(a["open_from"]), (ready + SETTLE_MIN) if ready else 0)
    others = [(tod(v.start), tod(v.end)) for v in it.visits if v.day == day]
    s = lo
    while s + a["visit_minutes"] <= min(hm(a["open_until"]), DAY_END_MIN):
        e = s + a["visit_minutes"]
        if all(e + VISIT_GAP_MIN <= os or s >= oe + VISIT_GAP_MIN for os, oe in others):
            return s
        s += 15
    choices = _free_start_choices(it, a, day, step=15)
    return choices[0] if choices else None


def op_add_attraction(it, op, cat, inv) -> List[str]:
    req = it.request
    a = cat.attractions.get(op.get("attraction_id"))
    if a is None:
        raise Refusal("ATTRACTION_NOT_FOUND", "We couldn't find that attraction.")
    day = _parse_date(op.get("date"))
    if day is None or not (req.start_date <= day < req.end_date):
        raise Refusal("INVALID_DAY", f"Attractions can be added on {req.start_date:%d %b} to "
                                     f"{(req.end_date - timedelta(days=1)):%d %b}. The last day is for going home.")
    city = night_city(it, day)
    if a["city"] != city:
        raise Refusal("ATTRACTION_WRONG_CITY", f"{a['name']} is in {a['city']}, but you stay in {city} on {day:%d %b}.",
                      f"Add it on a day you are in {a['city']}." if a["city"] in it.cities else None)
    if not attr.is_open_on(a, day):
        nxt = next((d for d in (req.start_date + timedelta(days=n) for n in range(req.nights))
                    if night_city(it, d) == a["city"] and attr.is_open_on(a, d)), None)
        raise Refusal("ATTRACTION_CLOSED", f"{a['name']} is closed on {day:%A %d %b}.",
                      f"It is open on {nxt:%A %d %b} — add it there?" if nxt else None)
    if any(v.attraction["attraction_id"] == a["attraction_id"] for v in it.visits):
        raise Refusal("ATTRACTION_DUPLICATE", f"{a['name']} is already in your holiday.")
    given = op.get("start")
    if given:
        try:
            s = hm(given)
        except Exception:
            raise Refusal("INVALID_TIME", "Start time must look like 14:30.")
        if s < hm(a["open_from"]) or s + a["visit_minutes"] > hm(a["open_until"]):
            raise Refusal("ATTRACTION_OUTSIDE_HOURS", f"{a['name']} is open {a['open_from']}–{a['open_until']} and the "
                                                      f"visit takes {a['visit_minutes']} minutes.")
        if s < _ready_min(it, day):
            raise Refusal("ATTRACTION_OUTSIDE_HOURS", f"You only reach this city around {time_label(at(day, _ready_min(it, day)))} "
                                                      f"on {day:%d %b}.")
        if s not in _free_start_choices(it, a, day, step=1):
            raise Refusal("ATTRACTION_OVERLAP", f"That time overlaps another visit on {day:%d %b}.",
                          "Pick another time or remove the other visit first.")
    else:
        s = _auto_start(it, a, day)
        if s is None:
            raise Refusal("ATTRACTION_OVERLAP", f"There is no free slot for {a['name']} on {day:%d %b}.",
                          "Try another day or remove a visit.")
    it.visits.append(Visit(a, at(day, s), at(day, s + a["visit_minutes"]), attraction_price(a, req.adults, req.children),
                           day, True))
    return []


def op_remove_attraction(it, op, cat, inv) -> List[str]:
    v = getattr(it, "visit_by_item", {}).get(op.get("item_id"))
    if v is None or v not in it.visits:
        raise Refusal("ITEM_NOT_FOUND", "We couldn't find that attraction in your holiday.")
    it.visits.remove(v)
    return []


OPS = {"CHANGE_HOTEL": op_change_hotel, "CHANGE_FLIGHT": op_change_flight,
       "ADD_ATTRACTION": op_add_attraction, "REMOVE_ATTRACTION": op_remove_attraction}


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
    return f"Attraction removed. {money}"


def apply_change(pkg: dict, op: dict, cat, inv, with_cheaper: bool = True) -> dict:
    """Apply one change to a stored package (never persists; the caller saves on APPLIED)."""
    if pkg.get("status") == "BOOKED":
        return Refusal("PACKAGE_LOCKED", "This holiday is already booked, so it can't be changed.").to_response()
    handler = OPS.get(op.get("op")) if isinstance(op, dict) else None
    if handler is None:
        return Refusal("UNKNOWN_OP", "Unknown change. Use CHANGE_HOTEL, CHANGE_FLIGHT, ADD_ATTRACTION or "
                                     "REMOVE_ATTRACTION.").to_response()
    it = itinerary_from_package(pkg, cat)
    try:
        extra_warnings = handler(it, op, cat, inv)
    except Refusal as r:
        return r.to_response("PINNED_CONFLICT" if r.code == "PINNED_CONFLICT" else "REFUSED")
    _recompute_metrics(it)
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
            if rooms_needed(room, adults, children) is None:
                continue                      # can never hold this party: not an option
            res = apply_change(pkg, {"op": "CHANGE_HOTEL", "city": city, "hotel_id": hotel["hotel_id"],
                                     "room_id": room["room_id"]}, cat, inv, with_cheaper=False)
            st = _status(res)
            if st["available"] and "_new_total" in st:
                st["price_delta_inr"] = st.pop("_new_total") - old_total
            k = rooms_needed(room, adults, children)
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
    day = _parse_date(day_text)
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
        choices = _free_start_choices(it, a, day)
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
