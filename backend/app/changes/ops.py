"""The five edits (hotel, flight, add/remove sight, city plan). Each mutates an itinerary and returns warnings,
or raises Refusal. Nothing here validates, prices against the budget or saves: see service.apply_change."""
from datetime import date, timedelta
from typing import List, Optional

from app.changes.refusal import Refusal
from app.changes.rebuild import (parse_date, ready_min, retime_arrival_day, night_city)
from app.config import DAY_END_MIN, DAY_START_MIN, SETTLE_MIN, VISIT_GAP_MIN
from app.core.pricing import attraction_price, hotel_price, rooms_needed
from app.core.timeutil import at, hm, tod
from app.engine import attractions as attr
from app.engine.airport import arrival_transfer, departure_transfer
from app.engine.models import Itinerary, TransferUse, TripRequest, Visit
from app.engine.variants import build_for_plan
from app.export.package import time_label


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
        warnings += retime_arrival_day(it, bool(op.get("remove_pinned_conflicts")))
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
        warnings += retime_arrival_day(it, bool(op.get("remove_pinned_conflicts")))
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


def free_start_choices(it: Itinerary, a: dict, day: date, step: int = 30) -> List[int]:
    """Start minutes (statement rules only) at which `a` fits on `day` without overlapping other visits."""
    ready = ready_min(it, day)
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
    ready = ready_min(it, day)
    lo = max(DAY_START_MIN, hm(a["open_from"]), (ready + SETTLE_MIN) if ready else 0)
    others = [(tod(v.start), tod(v.end)) for v in it.visits if v.day == day]
    s = lo
    while s + a["visit_minutes"] <= min(hm(a["open_until"]), DAY_END_MIN):
        e = s + a["visit_minutes"]
        if all(e + VISIT_GAP_MIN <= os or s >= oe + VISIT_GAP_MIN for os, oe in others):
            return s
        s += 15
    choices = free_start_choices(it, a, day, step=15)
    return choices[0] if choices else None


def op_add_attraction(it, op, cat, inv) -> List[str]:
    req = it.request
    a = cat.attractions.get(op.get("attraction_id"))
    if a is None:
        raise Refusal("ATTRACTION_NOT_FOUND", "We couldn't find that attraction.")
    day = parse_date(op.get("date"))
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
            raise Refusal("INVALID_TIME", "Start time must look like 14:30.") from None
        if s < hm(a["open_from"]) or s + a["visit_minutes"] > hm(a["open_until"]):
            raise Refusal("ATTRACTION_OUTSIDE_HOURS", f"{a['name']} is open {a['open_from']}–{a['open_until']} and the "
                                                      f"visit takes {a['visit_minutes']} minutes.")
        if s < ready_min(it, day):
            raise Refusal("ATTRACTION_OUTSIDE_HOURS", f"You only reach this city around {time_label(at(day, ready_min(it, day)))} "
                                                      f"on {day:%d %b}.")
        if s not in free_start_choices(it, a, day, step=1):
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


def request_from_package(pkg: dict) -> TripRequest:
    r = pkg["request"]
    return TripRequest(r["departure_city"], r["country"], date.fromisoformat(r["start_date"]), r["nights"],
                       r["adults"], tuple(r["child_ages"]), r["budget_inr"], r.get("traveler_name", "Traveler"))


def _adopt(it: Itinerary, new: Itinerary) -> None:
    """Replace the contents of `it` with a freshly built itinerary (same request)."""
    it.legs, it.arr_flight, it.ret_flight = new.legs, new.arr_flight, new.ret_flight
    it.arr_transfer, it.dep_transfer, it.links, it.visits = new.arr_transfer, new.dep_transfer, new.links, new.visits
    it.arr_pinned, it.ret_pinned = new.arr_pinned, new.ret_pinned
    it.visit_by_item = {}   # type: ignore[attr-defined]


def _carry_pinned(old: Itinerary, new: Itinerary, cat, inv, allow_remove: bool) -> List[str]:
    """Keep what the traveler chose (hotels, flights, attractions) wherever it is still valid in the new plan.

    Anything that cannot be kept is never dropped silently: the traveler is asked (PINNED_CONFLICT).
    """
    conflicts: List[str] = []
    warnings: List[str] = []
    for leg in old.legs:
        if not leg.pinned:
            continue
        same = next((x for x in new.legs if x.city == leg.city and x.nights == leg.nights
                     and x.check_in == leg.check_in), None)
        if same is None:
            conflicts.append(f"your stay at {leg.hotel['name']} in {leg.city}")
            continue
        try:
            warnings += op_change_hotel(new, {"city": leg.city, "hotel_id": leg.hotel["hotel_id"],
                                              "room_id": leg.room["room_id"]}, cat, inv)
        except Refusal:
            conflicts.append(f"your stay at {leg.hotel['name']} in {leg.city}")
    for tag, pinned, flight in (("ARRIVAL", old.arr_pinned, old.arr_flight), ("RETURN", old.ret_pinned, old.ret_flight)):
        if pinned:
            try:
                warnings += op_change_flight(new, {"leg": tag, "flight_id": flight["flight_id"]}, cat, inv)
            except Refusal:
                conflicts.append(f"your {tag.lower()} flight {flight['flight_number']}")
    for v in sorted(old.visits, key=lambda x: x.start):
        if not v.pinned:
            continue
        a = v.attraction
        start = f"{tod(v.start) // 60:02d}:{tod(v.start) % 60:02d}"
        for given in (start, None):
            op = {"attraction_id": a["attraction_id"], "date": v.day.isoformat()}
            if given:
                op["start"] = given
            try:
                op_add_attraction(new, op, cat, inv)
                break
            except Refusal as r:
                if r.code == "ATTRACTION_DUPLICATE":     # the new plan already includes it: keep it as the traveler's pick
                    for x in new.visits:
                        if x.attraction["attraction_id"] == a["attraction_id"]:
                            x.pinned = True
                    break
        else:
            conflicts.append(f"{a['name']} on {v.day:%d %b}")
    if conflicts and not allow_remove:
        raise Refusal(
            "PINNED_CONFLICT",
            "Switching the city plan can't keep: " + "; ".join(conflicts) + ".",
            "Keep your current plan, or switch and let those choices go.",
            [{"action": "KEEP_CURRENT"},
             {"action": "APPLY_AND_REMOVE", "remove": conflicts, "resend_with": {"remove_pinned_conflicts": True}}])
    warnings += [f"PINNED_DROPPED: {c} could not be kept in the new plan." for c in conflicts]
    return warnings


def op_change_city_plan(it, op, cat, inv) -> List[str]:
    raw = op.get("plan")
    hint = 'Give the plan as a list like [{"city": "Tokyo", "nights": 3}, {"city": "Kyoto", "nights": 3}].'
    if not isinstance(raw, list) or not raw:
        raise Refusal("INVALID_PLAN", "No city plan was given.", hint)
    try:
        plan = tuple((str(x["city"]), x["nights"]) for x in raw)
    except Exception:
        raise Refusal("INVALID_PLAN", "Each plan entry needs a city and a number of nights.", hint) from None
    if any(isinstance(n, bool) or not isinstance(n, int) for _, n in plan):
        raise Refusal("INVALID_PLAN", "Nights must be whole numbers.", hint)
    if sum(n for _, n in plan) != it.request.nights:
        raise Refusal("INVALID_PLAN", f"The nights in the plan must add up to your {it.request.nights} nights.", hint)
    new, _fits, err = build_for_plan(it.request, cat, inv, plan)
    if new is None:
        raise Refusal("INVALID_PLAN", err or "That city plan is not possible.",
                      "Pick one of the plans from the city-plan options.")
    warnings = _carry_pinned(it, new, cat, inv, bool(op.get("remove_pinned_conflicts")))
    _adopt(it, new)
    return warnings


OPS = {"CHANGE_HOTEL": op_change_hotel, "CHANGE_FLIGHT": op_change_flight,
       "ADD_ATTRACTION": op_add_attraction, "REMOVE_ATTRACTION": op_remove_attraction,
       "CHANGE_CITY_PLAN": op_change_city_plan}
