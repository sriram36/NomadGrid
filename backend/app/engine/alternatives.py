"""M8: when the request does not fit the budget, find what IS possible.

Levers (one at a time first, then combined): drop a city, fewer nights, shift the start date.
Every alternative is a full, validated Recommended package that fits the budget.
"""
from dataclasses import dataclass, replace
from datetime import timedelta
from typing import List

from app.config import WINDOW_FIRST, WINDOW_LAST
from app.engine.builder import build
from app.engine.results import BuildResult
from app.engine.cityplan import preferred_city_count
from app.engine.models import TripRequest


@dataclass
class Alternative:
    levers: List[str]
    label: str
    changes: List[dict]
    request: TripRequest
    result: BuildResult


def inr(n: int) -> str:
    """Indian digit grouping: 350000 -> '3,50,000'."""
    s = str(abs(int(n)))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return ("-" if n < 0 else "") + s


def _fits(res: BuildResult) -> bool:
    return res.outcome == "PACKAGE"


def _describe(levers, req, itinerary) -> str:
    cities = " + ".join(itinerary.cities)
    bits = []
    if "DROP_CITY" in levers:
        bits.append(f"Fewer cities ({cities})")
    if "FEWER_NIGHTS" in levers:
        bits.append(f"{req.nights} nights")
    if "SHIFT_DATE" in levers:
        bits.append(f"start on {req.start_date:%d %b}")
    return ", ".join(bits) + (f" · {req.nights} nights in {cities}" if "FEWER_NIGHTS" not in levers else f" in {cities}")


def find_alternatives(req: TripRequest, cat, inv, limit: int = 4) -> List[Alternative]:
    found: List[Alternative] = []
    kstar = preferred_city_count(req.nights, len(cat.cities_of(req.country)))

    def attempt(levers, r2: TripRequest, max_cities=None, changes=None) -> bool:
        res = build(r2, cat, inv, max_cities=max_cities)
        if not _fits(res):
            return False
        found.append(Alternative(levers, _describe(levers, r2, res.itinerary), changes or [], r2, res))
        return True

    def night_options(base_nights):
        return range(base_nights - 1, 2, -1)

    def date_options():
        for off in (1, -1, 2, -2, 3, -3):
            d = req.start_date + timedelta(days=off)
            if d >= WINDOW_FIRST and d + timedelta(days=req.nights) <= WINDOW_LAST:
                yield d

    # ---- single levers
    drop_cities = kstar - 1 if kstar > 1 else None
    if drop_cities:
        attempt(["DROP_CITY"], req, drop_cities,
                [{"field": "cities", "from": f"{kstar} cities", "to": f"at most {drop_cities}"}])
    for n in night_options(req.nights):
        if attempt(["FEWER_NIGHTS"], replace(req, nights=n),
                   changes=[{"field": "nights", "from": req.nights, "to": n}]):
            break
    for d in date_options():
        if attempt(["SHIFT_DATE"], replace(req, start_date=d),
                   changes=[{"field": "start_date", "from": req.start_date.isoformat(), "to": d.isoformat()}]):
            break

    # ---- combinations, only when no single lever worked
    if not found:
        if drop_cities:
            for n in night_options(req.nights):
                if attempt(["DROP_CITY", "FEWER_NIGHTS"], replace(req, nights=n), drop_cities,
                           [{"field": "cities", "from": f"{kstar} cities", "to": f"at most {drop_cities}"},
                            {"field": "nights", "from": req.nights, "to": n}]):
                    break
        for n in night_options(req.nights):
            hit = False
            for d in date_options():
                if attempt(["FEWER_NIGHTS", "SHIFT_DATE"], replace(req, nights=n, start_date=d) if d + timedelta(days=n) <= WINDOW_LAST else req,
                           changes=[{"field": "nights", "from": req.nights, "to": n},
                                    {"field": "start_date", "from": req.start_date.isoformat(), "to": d.isoformat()}]):
                    hit = True
                    break
            if hit:
                break
    return found[:limit]
