"""Package builder: chooses cities, flights, hotels, transfers and attractions.

Modes
  RECOMMENDED  best-quality package that fits the budget (PRD 6.10A) - the default
  CHEAPEST     lowest total price (also used to decide whether anything fits the budget)

Order of decisions for RECOMMENDED: constraints first (hard rules + budget), then the time-based
city count k*, then the time-equal band, then quality score.
"""
from dataclasses import dataclass, field
from datetime import date, timedelta
from itertools import product
from typing import Dict, List, Optional, Tuple

from app.config import DAY_END_MIN, DAY_START_MIN, SETTLE_MIN, TIME_TOLERANCE_MIN
from app.core.pricing import (
    attraction_price, flight_price, transfer_price, transfer_quantity,
)
from app.core.timeutil import tod
from app.engine import attractions as attr
from app.engine.cityplan import Plan, generate_plans, preferred_city_count
from app.engine.airport import best_airport_transfer
from app.engine.hotels import hotel_options, pareto
from app.engine.inventory import Inventory
from app.engine.models import Itinerary, Leg, TransferUse, TripRequest, Visit
from app.engine.schedule import arrival_pickup, departure_pickup, intercity_departure

FULL_DAY_MINUTES = DAY_END_MIN - DAY_START_MIN        # 780
WINDOW_FIRST, WINDOW_LAST = date(2027, 4, 1), date(2027, 4, 20)

STAGES = ["OUT_OF_WINDOW", "NO_ARRIVAL_FLIGHT", "INSUFFICIENT_SEATS_ARRIVAL", "NO_RETURN_FLIGHT",
          "INSUFFICIENT_SEATS_RETURN", "NO_CITY_PLAN_FOR_FLIGHTS", "NO_ROOMS", "NO_AIRPORT_TRANSFER",
          "NO_CITY_TRANSFER", "NOT_ENOUGH_ATTRACTIONS"]


# ============================================================================ result types
@dataclass
class BuildResult:
    outcome: str                       # PACKAGE | OVER_BUDGET | NO_PACKAGE
    itinerary: Optional[Itinerary] = None
    cheapest_total: Optional[int] = None
    reason_code: Optional[str] = None
    message: Optional[str] = None
    details: List[str] = field(default_factory=list)


class Diag:
    """Remembers the furthest stage any candidate reached; that explains a NO_PACKAGE."""

    def __init__(self):
        self.idx, self.code, self.message = -1, None, None

    def fail(self, code: str, message: str):
        i = STAGES.index(code)
        if i > self.idx:
            self.idx, self.code, self.message = i, code, message


# ============================================================================ plan context
class PlanCtx:
    def __init__(self, s: "Session", plan: Plan):
        self.s, self.plan = s, plan
        self.legs: List[Tuple[str, int, date, date]] = []
        d = s.req.start_date
        for city, n in plan:
            self.legs.append((city, n, d, d + timedelta(days=n)))
            d += timedelta(days=n)
        self.cities = [l[0] for l in self.legs]
        self.opts: List[List[dict]] = []
        self.fopts: List[List[dict]] = []
        self.links: List[Optional[dict]] = []
        self.arr_flights: List[dict] = []
        self.ret_flights: List[dict] = []
        self.full_days: List[Tuple[date, str]] = []
        self.change_days: List[Tuple[date, str]] = []
        self.attr_min = self.attr_rich = None
        self._arr_cache: Dict[tuple, Optional[tuple]] = {}
        self._dep_cache: Dict[tuple, Optional[tuple]] = {}
        self.ok = False

    # ------------------------------------------------------------------ building
    def prepare(self) -> bool:
        s, req = self.s, self.s.req
        first, last = self.cities[0], self.cities[-1]
        self.arr_flights = [f for f in s.arr_flights if first in s.cat.airports[f["to"]].get("serves_cities", [])]
        self.ret_flights = [f for f in s.ret_flights if last in s.cat.airports[f["from"]].get("serves_cities", [])]
        if not self.arr_flights or not self.ret_flights:
            s.diag.fail("NO_CITY_PLAN_FOR_FLIGHTS",
                        f"Arrival flights land at {self._airports(s.arr_flights, 'to')} and return flights leave from "
                        f"{self._airports(s.ret_flights, 'from')}, but no city plan can start in a city served by one "
                        f"and end in a city served by the other.")
            return False
        # hotels
        for i, (city, n, check_in, _) in enumerate(self.legs):
            stats: dict = {}
            options = s.hotels(city, check_in, n, stats)
            if not options:
                why = "no room type fits your group" if stats.get("sold_out", 0) == 0 else "the fitting rooms are sold out on some nights"
                s.diag.fail("NO_ROOMS", f"No hotel in {city} can take {req.adults} adult(s) and {req.children} child(ren) "
                                         f"for {n} night(s) from {check_in:%d %b} ({why}).")
                return False
            edge = i == 0 or i == len(self.legs) - 1
            self.opts.append(options)
            self.fopts.append(pareto(options, by_area=edge))
        # city transfers
        for i in range(len(self.legs) - 1):
            link = s.link(self.cities[i], self.cities[i + 1], self.legs[i + 1][2])
            if link is None:
                s.diag.fail("NO_CITY_TRANSFER", f"No transfer from {self.cities[i]} to {self.cities[i + 1]} "
                                                f"runs on {self.legs[i + 1][2]:%d %b}.")
                return False
            self.links.append(link)
            self.change_days.append((self.legs[i + 1][2], self.cities[i + 1]))
        # attractions for full days
        change = {d for d, _ in self.change_days}
        for city, n, check_in, check_out in self.legs:
            for j in range(n):
                d = check_in + timedelta(days=j)
                if d != req.start_date and d not in change:
                    self.full_days.append((d, city))
        for mode in ("MIN", "RICH"):
            plan_days = attr.plan_full_days(s.cat, self.full_days, req.adults, req.children, mode)
            if plan_days is None:
                s.diag.fail("NOT_ENOUGH_ATTRACTIONS", "There are not enough open attractions to fill every full day "
                                                      "of this city plan.")
                return False
            cost = attr.plan_cost(plan_days, req.adults, req.children)
            if mode == "MIN":
                self.attr_min = (plan_days, cost)
            else:
                self.attr_rich = (plan_days, cost)
        self.link_cost = sum(l["price"] for l in self.links)
        self.link_minutes = sum(l["rec"]["duration_minutes"] for l in self.links)
        self.change_usable = sum(self._usable_from(l["arrive"], d) for l, (d, _) in zip(self.links, self.change_days))
        self.ok = True
        return True

    @staticmethod
    def _airports(flights, key: str) -> str:
        return ", ".join(sorted({f[key] for f in flights})) or "none"

    @staticmethod
    def _usable_from(arrive, day: date) -> int:
        if arrive.date() != day:
            return 0
        lo = max(DAY_START_MIN, tod(arrive) + SETTLE_MIN)
        return max(0, DAY_END_MIN - lo)

    # ------------------------------------------------------------------ airport transfers
    def arr_transfer(self, flight: dict, opt: dict):
        key = (flight["flight_id"], opt["hotel"]["hotel_id"])
        if key not in self._arr_cache:
            self._arr_cache[key] = self._best_airport(flight["to"], self.cities[0], opt["hotel"]["area"],
                                                       lambda t: arrival_pickup(t, flight["_arr"]))
        return self._arr_cache[key]

    def dep_transfer(self, flight: dict, opt: dict):
        key = (flight["flight_id"], opt["hotel"]["hotel_id"])
        if key not in self._dep_cache:
            last_day = self.legs[-1][3]
            self._dep_cache[key] = self._best_airport(flight["from"], self.cities[-1], opt["hotel"]["area"],
                                                       lambda t: departure_pickup(t, flight["_dep"], last_day))
        return self._dep_cache[key]

    def _best_airport(self, airport: str, city: str, area: str, schedule):
        return best_airport_transfer(self.s.cat, self.s.req, airport, city, area, schedule)


# ============================================================================ session
class Session:
    def __init__(self, req: TripRequest, cat, inv: Inventory):
        self.req, self.cat, self.inv = req, cat, inv
        self.dep = cat.departure_airport(req.departure_city)
        self.code = cat.country_code(req.country)
        self.diag = Diag()
        self._hotels, self._links = {}, {}
        self.arr_flights: List[dict] = []
        self.ret_flights: List[dict] = []

    def hotels(self, city, check_in, nights, stats=None):
        key = (city, check_in, nights)
        if key not in self._hotels:
            st: dict = {}
            self._hotels[key] = (hotel_options(self.cat, self.inv, city, check_in, nights,
                                               self.req.adults, self.req.children, st), st)
        opts, st = self._hotels[key]
        if stats is not None:
            stats.update(st)
        return opts

    def link(self, a: str, b: str, day: date) -> Optional[dict]:
        key = (a, b, day)
        if key not in self._links:
            best = None
            for t in self.cat.link_transfers(self.req.country, a, b):
                times = intercity_departure(t, day)
                if times is None:
                    continue
                price = transfer_price(t, self.req.adults, self.req.children)
                k = (price, t["duration_minutes"], t["transfer_id"])
                if best is None or k < best[0]:
                    best = (k, {"rec": t, "pickup": times[0], "arrive": times[1], "price": price,
                                "quantity": transfer_quantity(t, self.req.adults, self.req.children),
                                "day": day, "from_city": a, "to_city": b})
            self._links[key] = best[1] if best else None
        return self._links[key]

    # ------------------------------------------------------------------ pre-checks
    def precheck(self) -> Optional[BuildResult]:
        r, cat = self.req, self.cat
        if r.start_date < WINDOW_FIRST or r.end_date > WINDOW_LAST:
            return BuildResult("NO_PACKAGE", reason_code="OUT_OF_WINDOW", message=(
                f"Our flights and rooms exist only from 1 to 20 April 2027. A {r.nights}-night trip starting "
                f"{r.start_date:%d %b %Y} would return on {r.end_date:%d %b %Y}; the first night must be on or after "
                f"1 Apr 2027 and the return flight on or before 20 Apr 2027."))
        arr_all = cat.arrivals(self.dep, self.code, r.start_date)
        if not arr_all:
            return self._none("NO_ARRIVAL_FLIGHT", f"No flights from {r.departure_city} to {r.country} land on "
                                                   f"{r.start_date:%d %b %Y}.")
        self.arr_flights = [f for f in arr_all if self.inv.seats_left(f) >= r.travelers]
        if not self.arr_flights:
            best = max(self.inv.seats_left(f) for f in arr_all)
            return self._none("INSUFFICIENT_SEATS_ARRIVAL",
                              f"{len(arr_all)} flight(s) from {r.departure_city} to {r.country} land on "
                              f"{r.start_date:%d %b %Y}, but none has {r.travelers} free seats (the best has {best}).")
        ret_all = cat.returns(self.dep, self.code, r.end_date)
        if not ret_all:
            return self._none("NO_RETURN_FLIGHT", f"No flights from {r.country} to {r.departure_city} leave on "
                                                  f"{r.end_date:%d %b %Y}.")
        self.ret_flights = [f for f in ret_all if self.inv.seats_left(f) >= r.travelers]
        if not self.ret_flights:
            best = max(self.inv.seats_left(f) for f in ret_all)
            return self._none("INSUFFICIENT_SEATS_RETURN",
                              f"{len(ret_all)} flight(s) from {r.country} to {r.departure_city} leave on "
                              f"{r.end_date:%d %b %Y}, but none has {r.travelers} free seats (the best has {best}).")
        return None

    @staticmethod
    def _none(code, msg):
        return BuildResult("NO_PACKAGE", reason_code=code, message=msg)


# ============================================================================ scoring helpers
def flight_points(a: dict, r: dict) -> float:
    pts = (5 if a["stops"] == 0 else 0) + (5 if r["stops"] == 0 else 0)
    pts += 5 if 360 <= tod(a["_arr"]) <= 1200 else 0
    pts += 5 if 480 <= tod(r["_dep"]) <= 1200 else 0
    return float(pts)


def experience_points(plan, full_days: int, children: int) -> float:
    atts = [a for v in plan.values() for a, _, _ in v]
    cov = min(1.0, len(atts) / (2 * full_days)) if full_days else 1.0
    variety = min(len({a["category"] for a in atts}), 4) / 4 if atts else 0.0
    if children == 0 or not atts:
        suit = 1.0
    else:
        suit = sum(1 for a in atts if a.get("child_friendly")) / len(atts)
    return 9 * cov + 3 * variety + 3 * suit


def time_points(transit: int, usable: int, n_days: int, tmin: int, tmax: int) -> float:
    t = 9.0 if tmax <= tmin else 9.0 * (1 - (transit - tmin) / (tmax - tmin))
    return max(0.0, min(9.0, t)) + 6.0 * min(1.0, usable / (FULL_DAY_MINUTES * n_days))


def fit_points(total: int, budget: int) -> float:
    return 10.0 * max(0.0, min(1.0, (total / budget - 0.5) / 0.4))


# ============================================================================ evaluation of one plan
def _cand(ctx, A, R, picks, arr, dep, mode, core, total, score, usable, transit):
    return {"A": A, "R": R, "picks": picks, "arr": arr, "dep": dep, "attr_mode": mode,
            "core": core, "total": total, "score": score, "usable": usable, "transit": transit}


def plan_transit_lo(ctx: PlanCtx) -> int:
    return min(a["duration_minutes"] + r["duration_minutes"] for a in ctx.arr_flights for r in ctx.ret_flights) \
        + ctx.link_minutes


def best_min_cost(ctx: PlanCtx) -> Optional[dict]:
    """Cheapest valid candidate for this plan (exact, separable search)."""
    req = ctx.s.req
    attr_cost = ctx.attr_min[1]
    k = len(ctx.legs)
    best = None

    def consider(A, R, picks, arr, dep, hotels_cost):
        nonlocal best
        core = (flight_price(A, req.travelers) + flight_price(R, req.travelers) + hotels_cost
                + arr[3] + dep[3] + ctx.link_cost)
        total = core + attr_cost
        key = (total, A["flight_id"], R["flight_id"], tuple(p["room"]["room_id"] for p in picks))
        if best is None or key < best[0]:
            transit = A["duration_minutes"] + R["duration_minutes"] + ctx.link_minutes
            best = (key, _cand(ctx, A, R, picks, arr, dep, "MIN", core, total, 0.0, 0, transit))

    if k == 1:
        for A in ctx.arr_flights:
            for R in ctx.ret_flights:
                for o in ctx.opts[0]:
                    arr, dep = ctx.arr_transfer(A, o), ctx.dep_transfer(R, o)
                    if arr and dep:
                        consider(A, R, [o], arr, dep, o["price"])
    else:
        mids = [min(opts, key=lambda o: (o["price"], o["hotel"]["hotel_id"], o["room"]["room_id"]))
                for opts in ctx.opts[1:-1]]
        mid_cost = sum(m["price"] for m in mids)
        first_best, last_best = {}, {}
        for A in ctx.arr_flights:
            c = [(o["price"] + ctx.arr_transfer(A, o)[3], o["hotel"]["hotel_id"], o["room"]["room_id"], o)
                 for o in ctx.opts[0] if ctx.arr_transfer(A, o)]
            if c:
                first_best[A["flight_id"]] = min(c, key=lambda x: x[:3])
        for R in ctx.ret_flights:
            c = [(o["price"] + ctx.dep_transfer(R, o)[3], o["hotel"]["hotel_id"], o["room"]["room_id"], o)
                 for o in ctx.opts[-1] if ctx.dep_transfer(R, o)]
            if c:
                last_best[R["flight_id"]] = min(c, key=lambda x: x[:3])
        for A in ctx.arr_flights:
            if A["flight_id"] not in first_best:
                continue
            for R in ctx.ret_flights:
                if R["flight_id"] not in last_best:
                    continue
                f, l = first_best[A["flight_id"]][3], last_best[R["flight_id"]][3]
                consider(A, R, [f] + mids + [l], ctx.arr_transfer(A, f), ctx.dep_transfer(R, l),
                         f["price"] + mid_cost + l["price"])
    if best is None:
        ctx.s.diag.fail("NO_AIRPORT_TRANSFER", "No airport transfer runs at a time that works with the available "
                                                "flights (pickup at least 60 minutes after landing, and arriving at "
                                                "the airport 3 hours before departure, inside service hours).")
        return None
    return best[1]


def best_recommended(ctx: PlanCtx, tr_range: Tuple[int, int]) -> Optional[dict]:
    """Highest-quality candidate for this plan that fits the budget."""
    s = ctx.s
    req, budget = s.req, s.req.budget_inr
    n_days = req.nights
    k = len(ctx.legs)
    nights = [l[1] for l in ctx.legs]
    full_n = len(ctx.full_days)
    exp = {"RICH": experience_points(ctx.attr_rich[0], full_n, req.children),
           "MIN": experience_points(ctx.attr_min[0], full_n, req.children)}
    acost = {"RICH": ctx.attr_rich[1], "MIN": ctx.attr_min[1]}
    tmin, tmax = tr_range
    full_usable = FULL_DAY_MINUTES * full_n + ctx.change_usable
    best = None

    def consider(A, R, picks, arr, dep, hotels_cost, stay_sum):
        nonlocal best
        core = (flight_price(A, req.travelers) + flight_price(R, req.travelers) + hotels_cost
                + arr[3] + dep[3] + ctx.link_cost)
        for mode in ("RICH", "MIN"):
            total = core + acost[mode]
            if total <= budget:
                break
        else:
            return
        transit = A["duration_minutes"] + R["duration_minutes"] + ctx.link_minutes
        usable = full_usable + ctx._usable_from(arr[2], req.start_date)
        score = (stay_sum / n_days + flight_points(A, R) + exp[mode]
                 + time_points(transit, usable, n_days, tmin, tmax) + fit_points(total, budget))
        key = (-round(score, 6), -total, A["flight_id"], R["flight_id"],
               tuple(p["room"]["room_id"] for p in picks))
        if best is None or key < best[0]:
            best = (key, _cand(ctx, A, R, picks, arr, dep, mode, core, total, score, usable, transit))

    min_hotels = sum(min(o["price"] for o in opts) for opts in ctx.opts)
    for A in ctx.arr_flights:
        for R in ctx.ret_flights:
            floor = (flight_price(A, req.travelers) + flight_price(R, req.travelers) + min_hotels
                     + ctx.link_cost + ctx.attr_min[1])
            if floor > budget:
                continue
            if k == 1:
                for o in ctx.fopts[0]:
                    arr, dep = ctx.arr_transfer(A, o), ctx.dep_transfer(R, o)
                    if arr and dep:
                        consider(A, R, [o], arr, dep, o["price"], o["sp"] * nights[0])
            else:
                mid_lists = ctx.fopts[1:-1]
                for f in ctx.fopts[0]:
                    arr = ctx.arr_transfer(A, f)
                    if not arr:
                        continue
                    for mids in product(*mid_lists):
                        for l in ctx.fopts[-1]:
                            dep = ctx.dep_transfer(R, l)
                            if not dep:
                                continue
                            picks = [f, *mids, l]
                            consider(A, R, picks, arr, dep, sum(p["price"] for p in picks),
                                     sum(p["sp"] * n for p, n in zip(picks, nights)))
    return best[1] if best else None


# ============================================================================ assembly of an itinerary
def finalize(ctx: PlanCtx, cand: dict, tr_range: Tuple[int, int], extras: bool) -> Itinerary:
    s = ctx.s
    req, cat = s.req, s.cat
    legs = [Leg(city=city, nights=n, check_in=ci, check_out=co, hotel=p["hotel"], room=p["room"],
                rooms=p["rooms"], price=p["price"])
            for (city, n, ci, co), p in zip(ctx.legs, cand["picks"])]
    A, R = cand["A"], cand["R"]
    t, pu, ar, pr, qty = cand["arr"]
    arr_t = TransferUse(t, pu, ar, pr, qty, req.start_date)
    t, pu, ar, pr, qty = cand["dep"]
    dep_t = TransferUse(t, pu, ar, pr, qty, ctx.legs[-1][3])
    links = [TransferUse(l["rec"], l["pickup"], l["arrive"], l["price"], l["quantity"], l["day"],
                         l["from_city"], l["to_city"]) for l in ctx.links]
    plan_days = (ctx.attr_rich if cand["attr_mode"] == "RICH" else ctx.attr_min)[0]
    visits: List[Visit] = []
    for d, items in plan_days.items():
        for a, s_min, e_min in items:
            visits.append(_visit(a, d, s_min, e_min, req))
    total = (flight_price(A, req.travelers) + flight_price(R, req.travelers) + sum(l.price for l in legs)
             + arr_t.price + dep_t.price + sum(l.price for l in links) + sum(v.price for v in visits))
    usable = cand["usable"]
    if extras and cand["attr_mode"] == "RICH":
        taken = {v.attraction["attraction_id"] for v in visits}
        spots = [(req.start_date, ctx.cities[0], arr_t.arrive)] + \
                [(d, city, l.arrive) for (d, city), l in zip(ctx.change_days, links)]
        for d, city, arrive in spots:
            if arrive.date() != d:
                continue
            got = attr.extra_visit(cat, city, d, tod(arrive), taken, req.adults, req.children,
                                   req.budget_inr - total)
            if got:
                a, s_min, e_min = got
                v = _visit(a, d, s_min, e_min, req)
                visits.append(v)
                taken.add(a["attraction_id"])
                total += v.price
    visits.sort(key=lambda v: v.start)
    it = Itinerary(request=req, legs=legs, arr_flight=A, ret_flight=R, arr_transfer=arr_t,
                   dep_transfer=dep_t, links=links, visits=visits)
    stars = sum(l.hotel["stars"] * l.nights for l in legs) / req.nights
    it.metrics = {
        "total": total, "transit_minutes": cand["transit"], "usable_ground_minutes": usable,
        "avg_hotel_stars": round(stars, 2), "quality_score": round(cand["score"], 1),
        "budget_used_pct": round(100.0 * total / req.budget_inr, 1),
        "attraction_mode": cand["attr_mode"],
    }
    return it


def _visit(a, day, s_min, e_min, req) -> Visit:
    from app.core.timeutil import at
    return Visit(a, at(day, s_min), at(day, e_min), attraction_price(a, req.adults, req.children), day)


# ============================================================================ public API
def _all_ctx(s: Session, max_cities: Optional[int]) -> Dict[int, List[PlanCtx]]:
    by_k: Dict[int, List[PlanCtx]] = {}
    for plan in generate_plans(s.cat, s.req.country, s.req.nights, max_cities):
        ctx = PlanCtx(s, plan)
        if ctx.prepare():
            by_k.setdefault(len(plan), []).append(ctx)
    return by_k


def _transit_range(by_k) -> Tuple[int, int]:
    vals = []
    for ctxs in by_k.values():
        for c in ctxs:
            for a in c.arr_flights:
                for r in c.ret_flights:
                    vals.append(a["duration_minutes"] + r["duration_minutes"] + c.link_minutes)
    return (min(vals), max(vals)) if vals else (0, 0)


def build(req: TripRequest, cat, inv: Optional[Inventory] = None, mode: str = "RECOMMENDED",
          max_cities: Optional[int] = None) -> BuildResult:
    inv = inv or Inventory(cat)
    s = Session(req, cat, inv)
    pre = s.precheck()
    if pre:
        return pre
    by_k = _all_ctx(s, max_cities)
    if not by_k:
        return BuildResult("NO_PACKAGE", reason_code=s.diag.code or "NO_CITY_PLAN_FOR_FLIGHTS",
                           message=s.diag.message or "No city plan fits these dates.")
    tr_range = _transit_range(by_k)

    # cheapest across everything: needed to tell OVER_BUDGET from NO_PACKAGE and for the CHEAPEST mode
    cheapest = None
    for ctxs in by_k.values():
        for c in ctxs:
            cand = best_min_cost(c)
            if cand and (cheapest is None or (cand["total"], c.plan) < (cheapest[1]["total"], cheapest[0].plan)):
                cheapest = (c, cand)
    if cheapest is None:
        return BuildResult("NO_PACKAGE", reason_code=s.diag.code or "NO_AIRPORT_TRANSFER",
                           message=s.diag.message or "No package can be built for this request.")
    c0, cand0 = cheapest
    if cand0["total"] > req.budget_inr:
        it = finalize(c0, cand0, tr_range, extras=False)
        return BuildResult("OVER_BUDGET", itinerary=it, cheapest_total=cand0["total"])
    if mode == "CHEAPEST":
        return BuildResult("PACKAGE", itinerary=finalize(c0, cand0, tr_range, extras=False),
                           cheapest_total=cand0["total"])

    # RECOMMENDED: k* first, then the time-equal band, then quality
    kstar = preferred_city_count(req.nights, len(cat.cities_of(req.country)))
    ks = sorted(by_k, key=lambda k: (abs(k - kstar), k > kstar))
    for k in ks:
        ctxs = by_k[k]
        best_t = min(plan_transit_lo(c) for c in ctxs)
        groups = [[c for c in ctxs if plan_transit_lo(c) <= best_t + TIME_TOLERANCE_MIN],
                  [c for c in ctxs if plan_transit_lo(c) > best_t + TIME_TOLERANCE_MIN]]
        for group in groups:
            winners = []
            for c in group:
                cand = best_recommended(c, tr_range)
                if cand:
                    winners.append((c, cand))
            if winners:
                c, cand = min(winners, key=lambda w: (-round(w[1]["score"], 6), -w[1]["total"], w[0].plan))
                it = finalize(c, cand, tr_range, extras=True)
                it.metrics["city_count_note"] = None if k == kstar else (
                    f"We preferred {kstar} city(ies) for {req.nights} nights, but only a {k}-city plan fits "
                    f"your budget and the available flights, rooms and attractions.")
                return BuildResult("PACKAGE", itinerary=it, cheapest_total=cand0["total"])
    # nothing scored (should not happen when the cheapest fits) -> fall back to the cheapest
    return BuildResult("PACKAGE", itinerary=finalize(c0, cand0, tr_range, extras=False), cheapest_total=cand0["total"])
