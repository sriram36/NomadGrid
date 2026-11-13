"""Independent rule validator (PRD 6.13).

Input is a trip in the shared export format plus the raw catalog - the same thing the judges' checker
sees. It deliberately re-derives every rule from scratch and does NOT use the builder's helpers.
It enforces ONLY the statement's rules (never our comfort preferences).
"""
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from math import ceil
from typing import List, Optional

WINDOW_FIRST, WINDOW_LAST = date(2027, 4, 1), date(2027, 4, 20)
REQUIRED = ["item_id", "type", "name", "city", "status", "catalog_id", "start", "end", "room_id",
            "quantity", "price_inr", "booking", "sources", "warnings"]
WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


@dataclass
class Violation:
    rule_id: str
    message: str
    item_id: Optional[str] = None

    def to_dict(self):
        return {"rule_id": self.rule_id, "message": self.message, "item_id": self.item_id}


def _mins(text: str) -> int:
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def _in_window(dt: datetime, frm: str, until: str) -> bool:
    s, e, m = _mins(frm), _mins(until), dt.hour * 60 + dt.minute
    if e >= s:
        return s <= m <= e or (e == 1440 and m == 0)
    return m >= s or m <= e


def _dt(text: str) -> datetime:
    return datetime.fromisoformat(text)


def validate_trip(trip: dict, cat, first_package: bool = False) -> List[Violation]:
    v: List[Violation] = []

    def bad(rule, msg, item=None):
        v.append(Violation(rule, msg, item.get("item_id") if isinstance(item, dict) else item))

    # ---------------------------------------------------------------- basic shape (E1)
    try:
        start, end = date.fromisoformat(trip["start_date"]), date.fromisoformat(trip["end_date"])
        trav = trip["traveler"]
        adults, children = int(trav["adults"]), int(trav["children"])
        home, country = trav["home_airport"], trip["country"]
        items = list(trip["items"])
    except Exception as e:   # noqa
        return [Violation("E1", f"Trip is malformed: {e!r}")]
    travelers = adults + children
    nights = (end - start).days
    code = cat.country_code(country)
    if code is None:
        bad("C1", f"Unknown country {country!r}")
        return v
    for i in items:
        missing = [k for k in REQUIRED if k not in i]
        if missing:
            bad("E1", f"Item is missing fields {missing}", i)
        elif i["sources"] != []:
            bad("E1", "sources must be an empty list", i)
    if any("type" not in i or "catalog_id" not in i for i in items):
        return v

    # ---------------------------------------------------------------- D: dates
    if not 3 <= nights <= 10:
        bad("D1", f"Trip has {nights} nights; must be 3 to 10")
    if start < WINDOW_FIRST:
        bad("D2", f"First night {start} is before 2027-04-01")
    if end > WINDOW_LAST:
        bad("D3", f"Return date {end} is after 2027-04-20")

    flights = [i for i in items if i["type"] == "flight"]
    hotels = sorted([i for i in items if i["type"] == "hotel"], key=lambda i: i["start"])
    transfers = [i for i in items if i["type"] == "transfer"]
    visits = [i for i in items if i["type"] == "attraction"]

    # ---------------------------------------------------------------- H + C: hotels & city plan
    legs = []
    for h in hotels:
        rec, room = cat.hotels.get(h["catalog_id"]), cat.rooms.get(h.get("room_id"))
        if rec is None:
            bad("H2", f"Unknown hotel {h['catalog_id']}", h)
            continue
        if room is None or room["hotel_id"] != rec["hotel_id"]:
            bad("H2", f"Room {h.get('room_id')} does not belong to hotel {rec['hotel_id']}", h)
            continue
        if h["city"] != rec["city"]:
            bad("H2", f"Hotel item city {h['city']} differs from the hotel's city {rec['city']}", h)
        ci, co = date.fromisoformat(h["start"]), date.fromisoformat(h["end"])
        k = h["quantity"]
        ma, mc = room["max_adults"], room["max_children"]
        if not (adults <= k * ma and adults + children <= k * (ma + mc) and adults >= k):
            bad("H4", f"{k} x {room['room_type']} cannot hold {adults} adult(s) + {children} child(ren)", h)
        for n in range((co - ci).days):
            d = ci + timedelta(days=n)
            if cat.rooms_left(room["room_id"], d) < k:
                bad("H5", f"Only {cat.rooms_left(room['room_id'], d)} room(s) left on {d}, need {k}", h)
        legs.append({"city": rec["city"], "ci": ci, "co": co, "hotel": rec, "item": h, "room": room, "k": k})
    if not legs:
        bad("H1", "No hotel in the package")
        return v
    if legs[0]["ci"] != start:
        bad("H3", f"First hotel check-in {legs[0]['ci']} is not the start date {start}")
    for a, b in zip(legs, legs[1:]):
        if a["co"] != b["ci"]:
            bad("H3", f"Hotel nights are not contiguous: {a['co']} vs {b['ci']}")
    if legs[-1]["co"] != end:
        bad("H3", f"Last hotel check-out {legs[-1]['co']} is not the return day {end}")
    cities = [l["city"] for l in legs]
    valid_cities = set(cat.cities_of(country))
    for l in legs:
        if l["city"] not in valid_cities:
            bad("C1", f"{l['city']} is not a city of {country}", l["item"])
        if (l["co"] - l["ci"]).days < 2:
            bad("C2", f"Only {(l['co'] - l['ci']).days} night(s) in {l['city']}; minimum is 2", l["item"])
    if len(set(cities)) != len(cities):
        bad("C3", f"A city appears more than once: {cities}")
    links = cat.links_of(country)
    for a, b in zip(cities, cities[1:]):
        if (a, b) not in links:
            bad("C4", f"No transfer link from {a} to {b}")
    if sum((l["co"] - l["ci"]).days for l in legs) != nights:
        bad("D4", "Hotel nights do not add up to the trip length")

    def night_city(d: date):
        for l in legs:
            if l["ci"] <= d < l["co"]:
                return l["city"]
        return None

    # ---------------------------------------------------------------- F: flights
    arr_items = [f for f in flights if cat.flights.get(f["catalog_id"], {}).get("from") == home]
    ret_items = [f for f in flights if cat.flights.get(f["catalog_id"], {}).get("to") == home]
    if len(flights) != 2 or len(arr_items) != 1 or len(ret_items) != 1:
        bad("F1", "Need exactly one arrival flight from the home airport and one return flight to it")
        arr_rec = ret_rec = None
    else:
        arr_rec, ret_rec = cat.flights[arr_items[0]["catalog_id"]], cat.flights[ret_items[0]["catalog_id"]]
        for it_, rec in ((arr_items[0], arr_rec), (ret_items[0], ret_rec)):
            if it_["start"][:16] != rec["departure_local"][:16] or it_["end"][:16] != rec["arrival_local"][:16]:
                bad("F1", "Flight times differ from the catalog", it_)
        if cat.country_of_airport(arr_rec["to"]) != code:
            bad("F2", f"Arrival flight lands in {arr_rec['to']}, not in {country}", arr_items[0])
        if cat.country_of_airport(ret_rec["from"]) != code:
            bad("F2", f"Return flight leaves from {ret_rec['from']}, not from {country}", ret_items[0])
        if _dt(arr_rec["arrival_local"]).date() != start:
            bad("F3", f"Arrival flight lands {arr_rec['arrival_local'][:10]}, not on the start date {start}", arr_items[0])
        if cities[0] not in cat.airports[arr_rec["to"]].get("serves_cities", []):
            bad("F4", f"{arr_rec['to']} does not serve the first city {cities[0]}", arr_items[0])
        if _dt(ret_rec["departure_local"]).date() != end:
            bad("F5", f"Return flight leaves {ret_rec['departure_local'][:10]}, not on the last day {end}", ret_items[0])
        if cities[-1] not in cat.airports[ret_rec["from"]].get("serves_cities", []):
            bad("F6", f"{ret_rec['from']} does not serve the last city {cities[-1]}", ret_items[0])
        for it_, rec in ((arr_items[0], arr_rec), (ret_items[0], ret_rec)):
            if rec["seats_left"] < travelers:
                bad("F7", f"Flight {rec['flight_id']} has {rec['seats_left']} seats, need {travelers}", it_)

    # ---------------------------------------------------------------- A + T: transfers
    airport_tr, city_tr = [], []
    for t in transfers:
        rec = cat.transfers.get(t["catalog_id"])
        if rec is None:
            bad("A1", f"Unknown transfer {t['catalog_id']}", t)
        elif rec.get("airport"):
            airport_tr.append((t, rec))
        elif rec.get("from_city"):
            city_tr.append((t, rec))
    airport_tr.sort(key=lambda x: x[0]["start"])
    city_tr.sort(key=lambda x: x[0]["start"])
    arrive_ready = None                     # when the traveler reaches the first hotel
    if len(airport_tr) != 2:
        bad("A1", f"Need exactly 2 airport transfers (arrival and departure), found {len(airport_tr)}")
    elif arr_rec is not None:
        (ta, ra), (td, rd) = airport_tr
        pa, pd_ = _dt(ta["start"]), _dt(td["start"])
        if ra["airport"] != arr_rec["to"]:
            bad("A2", f"Arrival transfer is from {ra['airport']}, flight lands at {arr_rec['to']}", ta)
        if rd["airport"] != ret_rec["from"]:
            bad("A2", f"Departure transfer goes to {rd['airport']}, flight leaves from {ret_rec['from']}", td)
        for t, rec, leg in ((ta, ra, legs[0]), (td, rd, legs[-1])):
            if rec["city"] != leg["city"] or rec["area"] not in (None, leg["hotel"]["area"]):
                bad("A3", f"{rec['transfer_id']} serves {rec['city']}/{rec['area']}, hotel is in "
                          f"{leg['city']}/{leg['hotel']['area']}", t)
        if pa < _dt(arr_rec["arrival_local"]) + timedelta(minutes=60):
            bad("A4", f"Pickup {ta['start']} is less than 60 minutes after landing {arr_rec['arrival_local']}", ta)
        if pd_ + timedelta(minutes=rd["duration_minutes"]) > _dt(ret_rec["departure_local"]) - timedelta(minutes=180):
            bad("A5", f"Traveler would reach the airport less than 180 minutes before departure", td)
        for t, rec in ((ta, ra), (td, rd)):
            if not _in_window(_dt(t["start"]), rec["service_from"], rec["service_until"]):
                bad("A6", f"Pickup {t['start']} is outside service hours {rec['service_from']}-{rec['service_until']}", t)
        if pd_.date() != end:
            bad("A7", f"Departure pickup {td['start']} is not on the last day {end}", td)
        arrive_ready = pa + timedelta(minutes=ra["duration_minutes"])
    if len(city_tr) != len(legs) - 1:
        bad("T1", f"Need {len(legs) - 1} transfer(s) between cities, found {len(city_tr)}")
    change_ready = {}
    for (t, rec), (a, b) in zip(city_tr, zip(legs, legs[1:])):
        p = _dt(t["start"])
        if (rec["from_city"], rec["to_city"]) != (a["city"], b["city"]):
            bad("T2", f"Transfer goes {rec['from_city']}→{rec['to_city']}, plan needs {a['city']}→{b['city']}", t)
        elif rec["transfer_id"] not in [x["transfer_id"] for x in cat.link_transfers(country, a["city"], b["city"])]:
            bad("T2", f"{rec['transfer_id']} is not a listed transfer for {a['city']}→{b['city']}", t)
        if p.date() != a["co"]:
            bad("T1", f"City transfer pickup {t['start']} is not on the change day {a['co']}", t)
        if not _in_window(p, rec["service_from"], rec["service_until"]):
            bad("T3", f"Departure {t['start']} is outside {rec['service_from']}-{rec['service_until']}", t)
        freq = rec.get("frequency_minutes")
        if freq and (p.hour * 60 + p.minute - _mins(rec["service_from"])) % freq != 0:
            bad("T3", f"Departure {t['start']} is not on the {freq}-minute timetable", t)
        change_ready[a["co"]] = p + timedelta(minutes=rec["duration_minutes"])

    # ---------------------------------------------------------------- X: attractions
    seen_ids, by_day = set(), {}
    for x in visits:
        rec = cat.attractions.get(x["catalog_id"])
        if rec is None:
            bad("X1", f"Unknown attraction {x['catalog_id']}", x)
            continue
        s_dt, e_dt = _dt(x["start"]), _dt(x["end"])
        d = s_dt.date()
        if d >= end:
            bad("X7", "No attractions on the last day", x)
            continue
        if d < start:
            bad("X1", f"Visit date {d} is before the trip", x)
            continue
        if x["catalog_id"] in seen_ids:
            bad("X6", f"{rec['name']} appears more than once", x)
        seen_ids.add(x["catalog_id"])
        if rec["city"] != night_city(d):
            bad("X2", f"{rec['name']} is in {rec['city']}, that night's hotel is in {night_city(d)}", x)
        if WEEKDAYS[d.weekday()] not in rec["open_days"] or d.isoformat() in rec.get("closed_dates", []):
            bad("X3", f"{rec['name']} is closed on {d}", x)
        sm, em = s_dt.hour * 60 + s_dt.minute, e_dt.hour * 60 + e_dt.minute
        if e_dt.date() != d or sm < _mins(rec["open_from"]) or em > _mins(rec["open_until"]):
            bad("X4", f"Visit {x['start']}-{x['end']} is outside opening hours {rec['open_from']}-{rec['open_until']}", x)
        if e_dt - s_dt != timedelta(minutes=rec["visit_minutes"]):
            bad("X4", f"Visit length is not {rec['visit_minutes']} minutes", x)
        ready = arrive_ready if d == start else change_ready.get(d)
        if ready is not None and s_dt < ready:
            bad("X8", f"Visit starts {x['start']} before the traveler reaches the city ({ready:%Y-%m-%d %H:%M})", x)
        by_day.setdefault(d, []).append((s_dt, e_dt, x))
    for d, lst in by_day.items():
        lst.sort(key=lambda r: r[0])
        for (s1, e1, a), (s2, e2, b) in zip(lst, lst[1:]):
            if s2 < e1:
                bad("X5", f"Visits overlap on {d}: {a['name']} and {b['name']}", b)
    if first_package:
        change_days = {l["co"] for l in legs[:-1]}
        d = start + timedelta(days=1)
        while d < end:
            if d not in change_days:
                n = len(by_day.get(d, []))
                if not 1 <= n <= 2:
                    bad("X9", f"Full day {d} has {n} attraction(s); the first package needs 1-2")
            d += timedelta(days=1)

    # ---------------------------------------------------------------- P: prices
    total = 0
    for i in items:
        total += i["price_inr"]
        t = i["type"]
        rec = {"flight": cat.flights, "hotel": cat.hotels, "transfer": cat.transfers,
               "attraction": cat.attractions}.get(t, {}).get(i["catalog_id"])
        if rec is None:
            continue
        expected = None
        if t == "flight":
            expected = rec["price_per_seat"]["amount"] * travelers
        elif t == "hotel":
            room = cat.rooms.get(i.get("room_id"))
            if room:
                nn = (date.fromisoformat(i["end"]) - date.fromisoformat(i["start"])).days
                expected = room["price_per_night"]["amount"] * i["quantity"] * nn
        elif t == "transfer":
            p = rec["price"]["amount"]
            if rec["pricing"] == "PER_VEHICLE":
                expected = p * ceil(travelers / rec["max_passengers"])
            else:
                cp = rec["child_price"]["amount"] if "child_price" in rec else p
                expected = adults * p + children * cp
        elif t == "attraction":
            p = rec["price_per_person"]["amount"]
            cp = rec["child_price"]["amount"] if "child_price" in rec else p
            expected = adults * p + children * cp
        if expected is not None and i["price_inr"] != expected:
            bad("P1", f"{t} price {i['price_inr']} should be {expected}", i)
    if trip.get("total_inr") != total:
        bad("P2", f"total_inr {trip.get('total_inr')} should equal the sum of item prices {total}")

    # ---------------------------------------------------------------- E2: booked state
    statuses = {i.get("status") for i in items}
    if "BOOKED" in statuses:
        refs = {(i.get("booking") or {}).get("reference") for i in items}
        if statuses != {"BOOKED"} or len(refs) != 1 or not all(isinstance(r, str) and re.fullmatch(r"\d{10}", r) for r in refs):
            bad("E2", "After confirm every item must be BOOKED with the same 10-digit booking.reference string")
    return v
