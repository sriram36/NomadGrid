"""Attraction planning.

Statement rules (hard): right city, open that weekday, not a closed date, whole visit inside
opening hours, no overlap, each attraction at most once, arrival/change-day visits start after
the traveler reaches the city.

Comfort rules (only for what the SYSTEM suggests): 08:30-21:30 window, 30-min gaps, 30-min settling.
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from app.config import DAY_END_MIN, DAY_START_MIN, SETTLE_MIN, VISIT_GAP_MIN
from app.core.pricing import attraction_price
from app.core.timeutil import at, hm, weekday_code

# date -> [(attraction, start_min, end_min)]
DayPlan = Dict[date, List[Tuple[dict, int, int]]]


def is_open_on(a: dict, day: date) -> bool:
    return weekday_code(day) in a["open_days"] and day.isoformat() not in a.get("closed_dates", [])


def candidates(cat, city: str, day: date, lo: int = DAY_START_MIN, hi: int = DAY_END_MIN) -> List[dict]:
    """Attractions in `city` that can be visited on `day` somewhere inside [lo, hi] minutes."""
    out = []
    for a in cat.attractions_in(city):
        if not is_open_on(a, day):
            continue
        start = max(hm(a["open_from"]), lo)
        latest_start = min(hm(a["open_until"]), hi) - a["visit_minutes"]
        if start <= latest_start:
            out.append(a)
    return out


def place_sequence(seq: List[dict], lo: int = DAY_START_MIN, hi: int = DAY_END_MIN,
                   gap: int = VISIT_GAP_MIN) -> Optional[List[Tuple[int, int]]]:
    """Earliest start/end minutes for visits in this order, or None if they don't fit the day."""
    out, cursor = [], lo
    for a in seq:
        start = max(cursor, hm(a["open_from"]))
        end = start + a["visit_minutes"]
        if end > min(hm(a["open_until"]), hi):
            return None
        out.append((start, end))
        cursor = end + gap
    return out


def _rank(a: dict, used_cats: Set[str], adults: int, children: int, mode: str):
    price = attraction_price(a, adults, children)
    if mode == "MIN":
        return (price, a["attraction_id"])
    kid_penalty = 0 if (children == 0 or a.get("child_friendly")) else 1
    return (kid_penalty, 1 if a["category"] in used_cats else 0, price, a["attraction_id"])


def _can_match(days: List[date], cands: Dict[date, List[dict]], taken: Set[str]) -> bool:
    """Can every day in `days` still get its own distinct attraction (bipartite matching)?"""
    match: Dict[str, date] = {}

    def try_day(d, seen):
        for a in cands[d]:
            aid = a["attraction_id"]
            if aid in taken or aid in seen:
                continue
            seen.add(aid)
            if aid not in match or try_day(match[aid], seen):
                match[aid] = d
                return True
        return False

    return all(try_day(d, set()) for d in days)


def plan_full_days(cat, full_days: List[Tuple[date, str]], adults: int, children: int,
                   mode: str) -> Optional[DayPlan]:
    """Attractions for every FULL day.

    mode "MIN": exactly one cheapest attraction per day (smallest possible cost).
    mode "RICH": one good attraction per day (varied, child-friendly), then a second where one fits.
    Returns None if some full day cannot get even one attraction.
    """
    cands = {d: candidates(cat, city, d) for d, city in full_days}
    days = [d for d, _ in full_days]
    order = sorted(days, key=lambda d: (len(cands[d]), d))
    taken: Set[str] = set()
    used_cats: Set[str] = set()
    chosen: Dict[date, dict] = {}
    for d in order:
        pool = sorted((a for a in cands[d] if a["attraction_id"] not in taken),
                      key=lambda a: _rank(a, used_cats, adults, children, mode))
        picked = None
        remaining = [x for x in days if x != d and x not in chosen]
        for a in pool:
            if _can_match(remaining, cands, taken | {a["attraction_id"]}):
                picked = a
                break
        if picked is None:
            return None
        chosen[d] = picked
        taken.add(picked["attraction_id"])
        used_cats.add(picked["category"])

    plan: DayPlan = {}
    for d in days:
        a1 = chosen[d]
        (s, e), = place_sequence([a1])
        plan[d] = [(a1, s, e)]

    if mode == "RICH":
        city_of = dict(full_days)
        for d in sorted(days):
            a1 = chosen[d]
            pool = [a for a in cands[d] if a["attraction_id"] not in taken]
            pool.sort(key=lambda a: _rank(a, used_cats, adults, children, mode))
            for a2 in pool:
                best = None
                for seq in ([a1, a2], [a2, a1]):
                    placed = place_sequence(seq)
                    if placed and (best is None or placed[-1][1] < best[1][-1][1]):
                        best = (seq, placed)
                if best:
                    seq, placed = best
                    plan[d] = [(a, s, e) for a, (s, e) in zip(seq, placed)]
                    taken.add(a2["attraction_id"])
                    used_cats.add(a2["category"])
                    break
    return plan


def plan_cost(plan: DayPlan, adults: int, children: int) -> int:
    return sum(attraction_price(a, adults, children) for v in plan.values() for a, _, _ in v)


def extra_visit(cat, city: str, day: date, ready_min: int, taken: Set[str], adults: int, children: int,
                budget_left: int) -> Optional[Tuple[dict, int, int]]:
    """One optional visit on an arrival/city-change day, starting after the traveler is ready.

    `ready_min` = minutes after midnight on `day` when the traveler reaches the city.
    """
    lo = max(DAY_START_MIN, ready_min + SETTLE_MIN)
    best = None
    for a in candidates(cat, city, day, lo=lo):
        if a["attraction_id"] in taken:
            continue
        price = attraction_price(a, adults, children)
        if price > budget_left:
            continue
        placed = place_sequence([a], lo=lo)
        if not placed:
            continue
        key = _rank(a, set(), adults, children, "RICH")
        if best is None or key < best[0]:
            best = (key, a, placed[0])
    if not best:
        return None
    _, a, (s, e) = best
    return a, s, e
