"""Turn an Itinerary into the API package object, and the package into the shared trip format."""
from datetime import date, datetime, timedelta
from typing import List, Optional

from app.core.pricing import flight_price
from app.core.timeutil import at, fmt_dt, hm, tod, weekday_code
from app.engine.models import Itinerary

EXPORT_FIELDS = ["item_id", "type", "name", "city", "status", "catalog_id", "start", "end", "room_id",
                 "quantity", "price_inr", "booking", "sources", "warnings"]


def time_label(dt: datetime) -> str:
    h = dt.hour % 12 or 12
    return f"{h}:{dt.minute:02d} {'am' if dt.hour < 12 else 'pm'}"


def _hours(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def _transfer_icon(rec: dict) -> str:
    t = rec["type"]
    if "TRAIN" in t:
        return "train"
    if "BUS" in t:
        return "bus"
    return "taxi"


def _transfer_sub(rec: dict, qty: int) -> str:
    if rec["pricing"] == "PER_VEHICLE":
        return f"{qty} vehicle(s) · up to {rec['max_passengers']} people each"
    return f"{qty} traveller(s) · priced per person"


def build_items(it: Itinerary, cat) -> List[dict]:
    n = it.request.travelers
    rows = []   # (sort datetime, item dict)

    def add(when, **item):
        item.setdefault("room_id", None)
        item.setdefault("badges", [])
        item.setdefault("image", None)
        rows.append((when, item))

    def city_name(code):
        return cat.airports[code]["city"]

    for flight, tag in ((it.arr_flight, "ARRIVAL"), (it.ret_flight, "RETURN")):
        city = city_name(flight["to"])     # data dictionary: "For a flight: the arrival city"
        add(flight["_dep"], type="flight", name=f"{flight['airline']} {flight['flight_number']} {flight['from']} to {flight['to']}",
            city=city, catalog_id=flight["flight_id"], start=fmt_dt(flight["_dep"]), end=fmt_dt(flight["_arr"]),
            quantity=n, price_inr=flight_price(flight, n), icon="flight", leg=tag,
            title=f"Flight {city_name(flight['from'])} → {city_name(flight['to'])}",
            subtitle=f"{flight['airline']} {flight['flight_number']} · {'Direct' if flight['stops'] == 0 else '1 stop'} · "
                     f"{_hours(flight['duration_minutes'])}",
            badges=["DIRECT" if flight["stops"] == 0 else "ONE_STOP"], time_dt=flight["_dep"],
            pinned=(it.arr_pinned if tag == "ARRIVAL" else it.ret_pinned),
            day=(flight["_arr"].date() if tag == "ARRIVAL" else flight["_dep"].date()))
    for tu, city, tag in ((it.arr_transfer, it.legs[0].city, "AIRPORT_ARRIVAL"), (it.dep_transfer, it.legs[-1].city, "AIRPORT_DEPARTURE")):
        add(tu.pickup, type="transfer", name=tu.rec["name"], city=city, catalog_id=tu.rec["transfer_id"],
            start=fmt_dt(tu.pickup), end=fmt_dt(tu.arrive), quantity=tu.quantity, price_inr=tu.price,
            icon=_transfer_icon(tu.rec), leg=tag, title=tu.rec["name"], subtitle=_transfer_sub(tu.rec, tu.quantity),
            time_dt=tu.pickup, day=tu.pickup.date())
    for l in it.links:
        add(l.pickup, type="transfer", name=l.rec["name"] if "name" in l.rec else f"{l.from_city} to {l.to_city}",
            city=l.to_city, catalog_id=l.rec["transfer_id"], start=fmt_dt(l.pickup), end=fmt_dt(l.arrive),
            quantity=l.quantity, price_inr=l.price, icon=_transfer_icon(l.rec), leg="INTERCITY",
            title=f"{l.from_city} → {l.to_city}", subtitle=_transfer_sub(l.rec, l.quantity),
            time_dt=l.pickup, day=l.pickup.date())
    for leg in it.legs:
        h = leg.hotel
        add(at(leg.check_in, hm(h["check_in_from"])), type="hotel", name=h["name"], city=leg.city,
            catalog_id=h["hotel_id"], room_id=leg.room["room_id"], start=leg.check_in.isoformat(),
            end=leg.check_out.isoformat(), quantity=leg.rooms, price_inr=leg.price, icon="hotel", leg="STAY",
            title=h["name"], subtitle=f"{leg.room['name']} × {leg.rooms} · {leg.nights} nights · {h['stars']}★ · {h['area']}",
            badges=["FAMILY_FRIENDLY"] if h.get("family_friendly") else [],
            image=("/" + h["image"]) if h.get("image") else None, pinned=leg.pinned,
            time_dt=at(leg.check_in, hm(h["check_in_from"])), day=leg.check_in)
    for v in it.visits:
        a = v.attraction
        badges = (["FREE"] if v.price == 0 else []) + (["CHILD_FRIENDLY"] if a.get("child_friendly") else [])
        add(v.start, type="attraction", name=a["name"], city=a["city"], catalog_id=a["attraction_id"],
            start=fmt_dt(v.start), end=fmt_dt(v.end), quantity=n, price_inr=v.price, icon="attraction", leg="VISIT",
            title=a["name"], subtitle=f"{a['visit_minutes']} min · {a['category'].replace('_', ' ').title()}",
            badges=badges, image=("/" + a["image"]) if a.get("image") else None,
            pinned=v.pinned, time_dt=v.start, day=v.day)
    rows.sort(key=lambda r: (r[0], r[1]["type"], r[1]["catalog_id"]))
    items = []
    for i, (_, item) in enumerate(rows, start=1):
        item.pop("time_dt", None)   # sort helper only; not JSON
        if isinstance(item.get("day"), date):
            item["day"] = item["day"].isoformat()
        item.update(item_id=f"i{i}", status="PLANNED", booking=None, sources=[], warnings=[])
        item.setdefault("pinned", False)
        items.append(item)
    return items


def build_days(it: Itinerary, items: List[dict], cat) -> List[dict]:
    req = it.request
    leg_of = {}
    for leg in it.legs:
        d = leg.check_in
        while d < leg.check_out:
            leg_of[d] = leg
            d += timedelta(days=1)
    change = {l.day for l in it.links}
    days = []
    d = req.start_date
    while d <= req.end_date:
        if d == req.end_date:
            kind, city = "LAST", it.legs[-1].city
        elif d == req.start_date:
            kind, city = "ARRIVAL", leg_of[d].city
        elif d in change:
            kind, city = "CITY_CHANGE", leg_of[d].city
        else:
            kind, city = "FULL", leg_of[d].city
        days.append({"date": d.isoformat(), "weekday": weekday_code(d), "city": city, "kind": kind, "events": []})
        d += timedelta(days=1)
    idx = {x["date"]: x for x in days}

    def event(day: date, when: datetime, item: dict, label: str):
        if day.isoformat() in idx:
            idx[day.isoformat()]["events"].append({"item_id": item["item_id"], "time": when.strftime("%H:%M"),
                                                   "time_label": time_label(when), "type": item["type"],
                                                   "icon": item["icon"], "label": label, "_t": when})
    for item in items:
        t = item["type"]
        if t == "flight":
            f = cat.flights[item["catalog_id"]]
            if item["leg"] == "ARRIVAL":
                event(f["_arr"].date(), f["_arr"], item, f"Land at {cat.airports[f['to']]['name']}")
            else:
                event(f["_dep"].date(), f["_dep"], item, f"Fly home from {cat.airports[f['from']]['name']}")
        elif t == "transfer":
            p = datetime.fromisoformat(item["start"])
            event(p.date(), p, item, item["title"])
        elif t == "attraction":
            p = datetime.fromisoformat(item["start"])
            event(p.date(), p, item, item["title"])
        elif t == "hotel":
            hotel = cat.hotels[item["catalog_id"]]
            ci, co = date.fromisoformat(item["start"]), date.fromisoformat(item["end"])
            event(ci, at(ci, hm(hotel["check_in_from"])), item, f"Check in · {item['title']}")
            out_at = at(co, hm(hotel["check_out_until"]))
            pickups = [datetime.fromisoformat(x["start"]) for x in items
                       if x["type"] == "transfer" and x["start"][:10] == co.isoformat()]
            if pickups:                       # you check out before the morning transfer leaves
                out_at = min(out_at, min(pickups) - timedelta(minutes=10))
            event(co, out_at, item, f"Check out · {item['title']}")
    for day in days:
        day["events"].sort(key=lambda e: e["_t"])
        for e in day["events"]:
            e.pop("_t")
        sights = sum(1 for e in day["events"] if e["type"] == "attraction")
        names = {"ARRIVAL": "Arrival day", "FULL": "Full day", "CITY_CHANGE": "Moving day", "LAST": "Going home"}
        day["summary"] = f"{names[day['kind']]} · {day['city']}" + (f" · {sights} sight(s)" if sights else "")
    return days


def soft_warnings(it: Itinerary) -> List[str]:
    out = []
    req = it.request
    note = it.metrics.get("city_count_note")
    if note:
        out.append(note)
    if len(it.legs) > 1 and sum(l.nights for l in it.legs) / len(it.legs) < 3:
        out.append("RUSHED_PLAN: this plan averages fewer than 3 nights per city.")
    for l in it.links:
        ready = tod(l.arrive) if l.arrive.date() == l.day else 1440
        if 1260 - ready < 240:
            out.append(f"LONG_TRANSIT_DAY: you reach {l.to_city} late on {l.day:%d %b}, leaving little time for sightseeing.")
    first = it.legs[0]
    if it.arr_transfer.arrive.date() == req.start_date and tod(it.arr_transfer.arrive) < hm(first.hotel["check_in_from"]):
        out.append(f"CHECKIN_TIME: you reach {first.hotel['name']} around {time_label(it.arr_transfer.arrive)}, "
                   f"before check-in opens at {first.hotel['check_in_from']}.")
    if req.children:
        for l in it.legs:
            if not l.hotel.get("family_friendly"):
                out.append(f"NOT_FAMILY_FRIENDLY: {l.hotel['name']} is not marked family friendly.")
        for v in it.visits:
            if not v.attraction.get("child_friendly"):
                out.append(f"NOT_FAMILY_FRIENDLY: {v.attraction['name']} is not marked child friendly.")
    change_days = {l.day for l in it.links}
    per_day = {}
    for v in it.visits:
        per_day[v.day] = per_day.get(v.day, 0) + 1
    d = req.start_date + timedelta(days=1)
    while d < req.end_date:
        n = per_day.get(d, 0)
        if d not in change_days and (n == 0 or n > 2):
            out.append(f"ATTRACTION_DAY_LOAD: {d:%a %d %b} has "
                       f"{'nothing planned' if n == 0 else f'{n} attractions planned'}.")
        d += timedelta(days=1)
    return out


def to_package(it: Itinerary, cat, package_id: str, traveler: dict, status: str = "PLANNED",
               reservation: Optional[dict] = None, variant: str = "DEFAULT") -> dict:
    req = it.request
    items = build_items(it, cat)
    days = build_days(it, items, cat)
    total = sum(i["price_inr"] for i in items)
    by_type = {"flights": 0, "hotels": 0, "transfers": 0, "attractions": 0}
    plural = {"flight": "flights", "hotel": "hotels", "transfer": "transfers", "attraction": "attractions"}
    for i in items:
        by_type[plural[i["type"]]] += i["price_inr"]
    metrics = {k: v for k, v in it.metrics.items() if k not in ("total", "city_count_note", "attraction_mode")}
    metrics["total"] = total
    metrics["budget_used_pct"] = round(100.0 * total / req.budget_inr, 1)
    return {
        "package_id": package_id, "status": status, "variant": variant, "traveler": traveler,
        "request": req.to_dict(), "country": req.country,
        "start_date": req.start_date.isoformat(), "end_date": req.end_date.isoformat(),
        "city_plan": [{"city": l.city, "nights": l.nights, "check_in": l.check_in.isoformat(),
                       "check_out": l.check_out.isoformat()} for l in it.legs],
        "pricing": {"total_inr": total, "budget_inr": req.budget_inr, "remaining_inr": req.budget_inr - total,
                    "over_budget": total > req.budget_inr, "breakdown": by_type},
        "metrics": metrics, "items": items, "days": days, "warnings": soft_warnings(it),
        "reservation": reservation,
    }


def to_trip_format(pkg: dict) -> dict:
    """The shared trip format used for export and for the independent validator."""
    status = pkg["status"]
    ref = pkg["reservation"]["number"] if pkg.get("reservation") else None
    items = []
    for i in pkg["items"]:
        row = {k: i.get(k) for k in EXPORT_FIELDS}
        row["sources"] = []
        row["warnings"] = list(i.get("warnings", []))
        row["status"] = status
        row["booking"] = {"reference": ref} if status == "BOOKED" and ref else None
        items.append(row)
    return {
        "trip_id": pkg["package_id"], "traveler": pkg["traveler"], "start_date": pkg["start_date"],
        "end_date": pkg["end_date"], "country": pkg["country"], "budget_inr": pkg["pricing"]["budget_inr"],
        "total_inr": sum(i["price_inr"] for i in pkg["items"]), "status": status, "items": items,
    }
