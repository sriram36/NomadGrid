"""Transfer timing: when can a transfer actually run?

All three functions return concrete local datetimes or None when impossible.
"""
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

from app.config import (
    AIRPORT_ARRIVE_BEFORE_MIN, ARRIVAL_PICKUP_BUFFER_MIN, EARLIEST_INTERCITY_DEPARTURE_MIN,
)
from app.core.timeutil import at, hm, in_window_dt

ONE_MIN = timedelta(minutes=1)


def _minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)


def arrival_pickup(transfer: dict, landing: datetime) -> Optional[Tuple[datetime, datetime]]:
    """Airport -> hotel. Earliest pickup >= landing + 60 min, inside the service window.

    The pickup must fall on the landing day (a window that wraps past midnight may spill
    into the next calendar day). Returns (pickup, arrival_at_hotel).
    """
    start, end = hm(transfer["service_from"]), hm(transfer["service_until"])
    end_eff = end if end >= start else end + 1440
    limit = at(landing.date(), max(1439, end_eff))
    base = _minute(landing)
    if landing.second or landing.microsecond:   # round a stray seconds value up to the next minute
        base += ONE_MIN
    p = base + timedelta(minutes=ARRIVAL_PICKUP_BUFFER_MIN)
    while p <= limit:
        if in_window_dt(p, start, end):
            return p, p + timedelta(minutes=transfer["duration_minutes"])
        p += ONE_MIN
    return None


def departure_pickup(transfer: dict, departure: datetime, last_day: date,
                     cushion_min: int = 15) -> Optional[Tuple[datetime, datetime]]:
    """Hotel -> airport. Latest pickup that still reaches the airport >= 180 min before departure.

    Pickup must be on the last day and inside the service window. We first try to keep a small
    cushion (system comfort); if that is infeasible we fall back to the exact statement limit.
    Returns (pickup, arrival_at_airport).
    """
    start, end = hm(transfer["service_from"]), hm(transfer["service_until"])
    floor_dt = at(last_day, 0)
    for cushion in (cushion_min, 0):
        p = _minute(departure) - timedelta(minutes=AIRPORT_ARRIVE_BEFORE_MIN + transfer["duration_minutes"] + cushion)
        while p >= floor_dt:
            if in_window_dt(p, start, end):
                return p, p + timedelta(minutes=transfer["duration_minutes"])
            p -= ONE_MIN
    return None


def intercity_departure(transfer: dict, day: date,
                        earliest_min: int = EARLIEST_INTERCITY_DEPARTURE_MIN) -> Optional[Tuple[datetime, datetime]]:
    """City -> city on the change day. Earliest departure >= comfort time (else the latest allowed).

    Trains/buses run every `frequency_minutes` from service_from; taxis can leave any minute
    inside the window. Returns (departure, arrival).
    """
    start, end = hm(transfer["service_from"]), hm(transfer["service_until"])
    if end < start:
        end += 1440
    freq = transfer.get("frequency_minutes")
    if freq:
        slots = list(range(start, end + 1, freq))
    else:
        slots = [max(start, earliest_min)] if max(start, earliest_min) <= end else [end]
    if not slots:
        return None
    pick = next((s for s in slots if s >= earliest_min), slots[-1])
    dep = at(day, pick)
    return dep, dep + timedelta(minutes=transfer["duration_minutes"])
