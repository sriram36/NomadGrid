"""S6: the journey as a map-ready route: departure hub, cities in visit order, the legs between them.

Built from the itinerary every time a package is built or changed, so it always matches what the traveler sees
(switching a variant or customising a stop simply returns a new package with a new route). Coordinates come from
the catalog (airports and the chosen hotels); nothing here is stored or written back to the data files.
"""
from typing import List

from app.engine.models import Itinerary

_MODE = {"TRAIN": "TRAIN", "INTERCITY_BUS": "BUS", "CITY_BUS": "BUS", "INTERCITY_TAXI": "TAXI", "CITY_TAXI": "TAXI"}


def _hours(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def build_route(it: Itinerary, cat) -> dict:
    req = it.request
    origin_code = cat.departure_airport(req.departure_city)
    origin_airport = cat.airports[origin_code] if origin_code else {}
    stops: List[dict] = []
    for i, leg in enumerate(it.legs, start=1):
        stops.append({"order": i, "city": leg.city, "nights": leg.nights, "check_in": leg.check_in.isoformat(),
                      "check_out": leg.check_out.isoformat(), "hotel": leg.hotel["name"],
                      "lat": leg.hotel.get("lat"), "lng": leg.hotel.get("lng")})

    def flight_leg(flight: dict, direction: str, origin_side: str) -> dict:
        a_from, a_to = cat.airports[flight["from"]], cat.airports[flight["to"]]
        return {"kind": "FLIGHT", "direction": direction, "mode": "FLIGHT",
                "from": a_from["city"], "to": a_to["city"], "from_code": flight["from"], "to_code": flight["to"],
                "label": f"{flight['airline']} {flight['flight_number']}", "stops": flight["stops"],
                "duration_minutes": flight["duration_minutes"], "duration_label": _hours(flight["duration_minutes"]),
                "depart": flight["departure_local"], "arrive": flight["arrival_local"], "side": origin_side}

    legs = [flight_leg(it.arr_flight, "OUT", "start")]
    for link in it.links:
        rec = link.rec
        legs.append({"kind": "INTERCITY", "direction": "ONWARD", "mode": _MODE.get(rec["type"], "TRANSFER"),
                     "from": link.from_city, "to": link.to_city, "label": rec["name"],
                     "duration_minutes": rec["duration_minutes"], "duration_label": _hours(rec["duration_minutes"])})
    legs.append(flight_leg(it.ret_flight, "BACK", "end"))
    for i, leg in enumerate(legs, start=1):
        leg["order"] = i

    travel = sum(l["duration_minutes"] for l in legs)
    path = [req.departure_city] + [s["city"] for s in stops] + [req.departure_city]
    return {
        "origin": {"city": req.departure_city, "airport": origin_code, "airport_name": origin_airport.get("name"),
                   "lat": origin_airport.get("lat"), "lng": origin_airport.get("lng")},
        "stops": stops, "legs": legs, "path": path,
        "summary": {"cities": len(stops), "nights": req.nights, "travel_minutes": travel,
                    "travel_label": _hours(travel), "label": " → ".join(path)},
    }
