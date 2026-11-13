"""Turn a stored package back into an editable itinerary, and keep its derived numbers up to date."""
from datetime import date, datetime
from typing import Dict, List, Optional

from app.changes.refusal import Refusal
from app.core.timeutil import at, hm, tod
from app.engine.models import Itinerary, Leg, TransferUse, TripRequest, Visit
from app.export.package import time_label


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
    assert arr and ret and arr_t and dep_t, "package is missing a flight or an airport transfer"
    it = Itinerary(req, legs, arr, ret, arr_t, dep_t, links, visits, {}, arr_pinned, ret_pinned)
    it.visit_by_item = visit_by_item   # type: ignore[attr-defined]
    return it


def recompute_metrics(it: Itinerary):
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


def ready_min(it: Itinerary, day: date) -> int:
    """Minutes after midnight on `day` when the traveler is in that day's city (0 = from the start)."""
    if day == it.request.start_date:
        arrive = it.arr_transfer.arrive
    else:
        arrive = next((l.arrive for l in it.links if l.day == day), None)
    if arrive is None:
        return 0
    return tod(arrive) if arrive.date() == day else 1440


def retime_arrival_day(it: Itinerary, allow_remove: bool) -> List[str]:
    """After the arrival moved: shift arrival-day visits that no longer fit; never drop a pinned one silently."""
    day = it.request.start_date
    ready = ready_min(it, day)
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


def parse_date(text) -> Optional[date]:
    try:
        return date.fromisoformat(text)
    except Exception:
        return None
