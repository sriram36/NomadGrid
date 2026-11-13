"""Choose the airport transfer for a flight + hotel (shared by the builder and by package changes)."""
from datetime import date, datetime
from typing import Callable, Optional, Tuple

from app.core.pricing import transfer_price, transfer_quantity
from app.engine.models import TripRequest
from app.engine.schedule import arrival_pickup, departure_pickup

# (transfer record, pickup, arrival, price, quantity)
Choice = Tuple[dict, datetime, datetime, int, int]


def best_airport_transfer(cat, req: TripRequest, airport: str, city: str, area: str,
                          schedule: Callable) -> Optional[Choice]:
    """Cheapest transfer that serves airport + city + hotel area and can run at a valid time."""
    best = None
    for t in cat.airport_transfers(airport, city):
        if t["area"] not in (None, area):
            continue
        times = schedule(t)
        if times is None:
            continue
        price = transfer_price(t, req.adults, req.children)
        key = (price, t["transfer_id"])
        if best is None or key < best[0]:
            best = (key, (t, times[0], times[1], price, transfer_quantity(t, req.adults, req.children)))
    return best[1] if best else None


def arrival_transfer(cat, req, flight: dict, city: str, area: str) -> Optional[Choice]:
    return best_airport_transfer(cat, req, flight["to"], city, area, lambda t: arrival_pickup(t, flight["_arr"]))


def departure_transfer(cat, req, flight: dict, city: str, area: str, last_day: date) -> Optional[Choice]:
    return best_airport_transfer(cat, req, flight["from"], city, area,
                                 lambda t: departure_pickup(t, flight["_dep"], last_day))
