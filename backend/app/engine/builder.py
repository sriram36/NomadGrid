"""Package builder: chooses cities, flights, hotels, transfers and attractions.

Modes
  RECOMMENDED  best-quality package that fits the budget (PRD 6.10A) - the default
  CHEAPEST     lowest total price (also used to decide whether anything fits the budget)

Order of decisions for RECOMMENDED: constraints first (hard rules + budget), then the time-based
city count k*, then the time-equal band, then quality score.
"""
from itertools import product
from typing import Dict, List, Optional, Tuple

from app.config import TIME_TOLERANCE_MIN
from app.core.pricing import (
    attraction_price, flight_price,
)
from app.core.timeutil import tod
from app.engine import attractions as attr
from app.engine.cityplan import generate_plans, preferred_city_count
from app.engine.inventory import Inventory
from app.engine.models import Itinerary, Leg, TransferUse, TripRequest, Visit
from app.engine.context import PlanCtx, Session
from app.engine.results import BuildResult
from app.engine.scoring import FULL_DAY_MINUTES, experience_points, fit_points, flight_points, time_points


# ============================================================================ evaluation of one plan
def candidate(ctx, A, R, picks, arr, dep, mode, core, total, score, usable, transit):
    return {"A": A, "R": R, "picks": picks, "arr": arr, "dep": dep, "attr_mode": mode,
            "core": core, "total": total, "score": score, "usable": usable, "transit": transit}


def plan_transit_lo(ctx: PlanCtx) -> int:
    return min(a["duration_minutes"] + r["duration_minutes"] for a in ctx.arr_flights for r in ctx.ret_flights) \
        + ctx.link_minutes


def best_min_cost(ctx: PlanCtx, pair_ok=None) -> Optional[dict]:
    """Cheapest valid candidate for this plan (exact, separable search).

    `pair_ok(arrival_flight, return_flight)` optionally restricts which flight pairs may be used.
    """
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
            best = (key, candidate(ctx, A, R, picks, arr, dep, "MIN", core, total, 0.0, 0, transit))

    if k == 1:
        for A in ctx.arr_flights:
            for R in ctx.ret_flights:
                if pair_ok and not pair_ok(A, R):
                    continue
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
            c = [(o["price"] + t[3], o["hotel"]["hotel_id"], o["room"]["room_id"], o)
                 for o in ctx.opts[0] if (t := ctx.arr_transfer(A, o))]
            if c:
                first_best[A["flight_id"]] = min(c, key=lambda x: x[:3])
        for R in ctx.ret_flights:
            c = [(o["price"] + t[3], o["hotel"]["hotel_id"], o["room"]["room_id"], o)
                 for o in ctx.opts[-1] if (t := ctx.dep_transfer(R, o))]
            if c:
                last_best[R["flight_id"]] = min(c, key=lambda x: x[:3])
        for A in ctx.arr_flights:
            if A["flight_id"] not in first_best:
                continue
            for R in ctx.ret_flights:
                if R["flight_id"] not in last_best or (pair_ok and not pair_ok(A, R)):
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
            best = (key, candidate(ctx, A, R, picks, arr, dep, mode, core, total, score, usable, transit))

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
                                     sum(p["sp"] * n for p, n in zip(picks, nights, strict=False)))
    return best[1] if best else None


# ============================================================================ assembly of an itinerary
def finalize(ctx: PlanCtx, cand: dict, tr_range: Tuple[int, int], extras: bool) -> Itinerary:
    s = ctx.s
    req, cat = s.req, s.cat
    legs = [Leg(city=city, nights=n, check_in=ci, check_out=co, hotel=p["hotel"], room=p["room"],
                rooms=p["rooms"], price=p["price"])
            for (city, n, ci, co), p in zip(ctx.legs, cand["picks"], strict=False)]
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
                [(d, city, l.arrive) for (d, city), l in zip(ctx.change_days, links, strict=False)]
        for d, city, arrive in spots:
            if arrive.date() != d:
                continue
            got = attr.extra_visit(cat, city, d, tod(arrive), taken, req.adults, req.children,
                                   req.budget_inr - total, req.interests)
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


def prepare_all(req: TripRequest, cat, inv: Optional[Inventory] = None, max_cities: Optional[int] = None):
    """The first half of every build: prechecks, every plan context, and the cheapest candidate overall.

    Returns (early_result, None) when the request ends here (NO_PACKAGE), otherwise
    (None, (session, plans_by_city_count, transit_range, cheapest_ctx, cheapest_candidate)).
    """
    inv = inv or Inventory(cat)
    s = Session(req, cat, inv)
    pre = s.precheck()
    if pre:
        return pre, None
    by_k = _all_ctx(s, max_cities)
    if not by_k:
        return BuildResult("NO_PACKAGE", reason_code=s.diag.code or "NO_CITY_PLAN_FOR_FLIGHTS",
                           message=s.diag.message or "No city plan fits these dates."), None
    tr_range = _transit_range(by_k)
    cheapest = None
    for ctxs in by_k.values():
        for c in ctxs:
            cand = best_min_cost(c)
            if cand and (cheapest is None or (cand["total"], c.plan) < (cheapest[1]["total"], cheapest[0].plan)):
                cheapest = (c, cand)
    if cheapest is None:
        return BuildResult("NO_PACKAGE", reason_code=s.diag.code or "NO_AIRPORT_TRANSFER",
                           message=s.diag.message or "No package can be built for this request."), None
    return None, (s, by_k, tr_range, cheapest[0], cheapest[1])


def build(req: TripRequest, cat, inv: Optional[Inventory] = None, mode: str = "RECOMMENDED",
          max_cities: Optional[int] = None) -> BuildResult:
    early, prep = prepare_all(req, cat, inv, max_cities)
    if early is not None:
        return early
    assert prep is not None
    s, by_k, tr_range, c0, cand0 = prep
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
