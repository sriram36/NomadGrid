"""G4 package variants (cheapest / best rated, plus the recommended one) and G3 city-plan options.

Definitions (problem statement):
  cheapest    lowest total price
  best rated  highest average hotel `stars` per night, within budget (guest `rating` does not count)
On a tie either package may be shown; we break ties by the lower price.
"""
from itertools import product
from typing import Dict, List, Optional, Tuple

from app.core.pricing import flight_price
from app.engine.builder import candidate, best_min_cost, best_recommended, finalize, prepare_all
from app.engine.context import PlanCtx
from app.engine.results import BuildResult
from app.engine.scoring import FULL_DAY_MINUTES, experience_points, fit_points, flight_points, time_points
from app.engine.cityplan import Plan, preferred_city_count
from app.engine.inventory import Inventory
from app.engine.models import Itinerary, TripRequest


# ============================================================================ shared helpers
def score_candidate(ctx: PlanCtx, cand: dict, tr_range: Tuple[int, int]) -> Tuple[float, int]:
    """Quality score and usable ground minutes for any candidate (so every variant reports comparable metrics)."""
    req = ctx.s.req
    nights = [l[1] for l in ctx.legs]
    stay = sum(p["sp"] * n for p, n in zip(cand["picks"], nights, strict=True)) / req.nights
    plan = (ctx.attr_rich if cand["attr_mode"] == "RICH" else ctx.attr_min)[0]
    exp = experience_points(plan, len(ctx.full_days), req.children)
    usable = (FULL_DAY_MINUTES * len(ctx.full_days) + ctx.change_usable
              + ctx._usable_from(cand["arr"][2], req.start_date))
    tmin, tmax = tr_range
    score = (stay + flight_points(cand["A"], cand["R"]) + exp
             + time_points(cand["transit"], usable, req.nights, tmin, tmax) + fit_points(cand["total"], req.budget_inr))
    return score, usable


def _polish(ctx: PlanCtx, cand: dict, tr_range: Tuple[int, int]) -> dict:
    """Use two attractions a day when the budget allows (else one), then fill in the metrics."""
    budget = ctx.s.req.budget_inr
    out = dict(cand)
    rich_total = out["core"] + ctx.attr_rich[1]
    if rich_total <= budget:
        out.update(attr_mode="RICH", total=rich_total)
    else:
        out.update(attr_mode="MIN", total=out["core"] + ctx.attr_min[1])
    out["score"], out["usable"] = score_candidate(ctx, out, tr_range)
    return out


# ============================================================================ best rated
def _transit(ctx: PlanCtx, a: dict, r: dict) -> int:
    return a["duration_minutes"] + r["duration_minutes"] + ctx.link_minutes


def _stars_pareto(options: List[dict], by_area: bool) -> List[dict]:
    """Keep options not dominated on (price lower, stars higher); per area for the first/last city."""
    groups: Dict[Optional[str], List[dict]] = {}
    for o in options:
        groups.setdefault(o["area"] if by_area else None, []).append(o)
    kept = []
    for g in groups.values():
        g.sort(key=lambda o: (o["price"], -o["hotel"]["stars"], o["hotel"]["hotel_id"], o["room"]["room_id"]))
        best = -1
        for o in g:
            if o["hotel"]["stars"] > best:
                kept.append(o)
                best = o["hotel"]["stars"]
    return kept


def _best_stars_for(ctx: PlanCtx) -> Optional[dict]:
    """Most star-nights within budget for this plan; ties go to the lower total."""
    req = ctx.s.req
    budget = req.budget_inr
    nights = [l[1] for l in ctx.legs]
    k = len(ctx.legs)
    fopts = [_stars_pareto(o, by_area=(i == 0 or i == k - 1)) for i, o in enumerate(ctx.opts)]
    attr_cost = ctx.attr_min[1]
    best: Optional[tuple] = None

    def consider(a, r, picks, arr, dep):
        nonlocal best
        core = (flight_price(a, req.travelers) + flight_price(r, req.travelers) + sum(p["price"] for p in picks)
                + arr[3] + dep[3] + ctx.link_cost)
        total = core + attr_cost
        if total > budget:
            return
        star_nights = sum(p["hotel"]["stars"] * n for p, n in zip(picks, nights, strict=True))
        key = (-star_nights, total, a["flight_id"], r["flight_id"], tuple(p["room"]["room_id"] for p in picks))
        if best is None or key < best[0]:
            cand = candidate(ctx, a, r, picks, arr, dep, "MIN", core, total, 0.0, 0, _transit(ctx, a, r))
            cand["star_nights"] = star_nights
            best = (key, cand)

    for a in ctx.arr_flights:
        for r in ctx.ret_flights:
            if k == 1:
                for o in fopts[0]:
                    arr, dep = ctx.arr_transfer(a, o), ctx.dep_transfer(r, o)
                    if arr and dep:
                        consider(a, r, [o], arr, dep)
            else:
                for f in fopts[0]:
                    arr = ctx.arr_transfer(a, f)
                    if not arr:
                        continue
                    for mids in product(*fopts[1:-1]):
                        for last in fopts[-1]:
                            dep = ctx.dep_transfer(r, last)
                            if dep:
                                consider(a, r, [f, *mids, last], arr, dep)
    return best[1] if best else None


def _best_rated(by_k: Dict[int, List[PlanCtx]]) -> Optional[Tuple[PlanCtx, dict]]:
    best = None
    for ctxs in by_k.values():
        for c in ctxs:
            cand = _best_stars_for(c)
            if cand is None:
                continue
            key = (-cand["star_nights"], cand["total"], c.plan)
            if best is None or key < best[0]:
                best = (key, c, cand)
    return (best[1], best[2]) if best else None


# ============================================================================ G4 entry point
def build_variants(req: TripRequest, cat, inv: Optional[Inventory] = None) -> dict:
    """Returns {"early": BuildResult} when there is no package, else {"variants": {...}, "notes": [...]}."""
    early, prep = prepare_all(req, cat, inv)
    if early is not None:
        return {"early": early}
    assert prep is not None
    s, by_k, tr, c0, cand0 = prep
    if cand0["total"] > req.budget_inr:
        return {"early": BuildResult("OVER_BUDGET", itinerary=finalize(c0, cand0, tr, extras=False),
                                     cheapest_total=cand0["total"])}
    found: Dict[str, Optional[Itinerary]] = {}

    cheap = dict(cand0)
    cheap["score"], cheap["usable"] = score_candidate(c0, cheap, tr)
    found["cheapest"] = finalize(c0, cheap, tr, extras=False)

    rated = _best_rated(by_k)
    found["best_rated"] = finalize(rated[0], _polish(rated[0], rated[1], tr), tr, extras=True) if rated else None

    notes: List[str] = []
    if found["best_rated"] is None:
        notes.append("No best-rated package fits your budget, so only the other choices are shown.")

    def sig(it: Optional[Itinerary]):
        if it is None:
            return None
        return (tuple((l.city, l.nights, l.hotel["hotel_id"], l.room["room_id"]) for l in it.legs),
                it.arr_flight["flight_id"], it.ret_flight["flight_id"])
    if found["best_rated"] and sig(found["best_rated"]) == sig(found["cheapest"]):
        notes.append("The cheapest package is also the best rated.")
    return {"variants": found, "notes": notes}


# ============================================================================ G3 city plans
def _plan_dicts(plan: Plan) -> List[dict]:
    return [{"city": c, "nights": n} for c, n in plan]


def plan_options(req: TripRequest, cat, inv: Optional[Inventory] = None) -> dict:
    """Every valid city plan with the package total it would give (best quality that fits the budget,
    else the cheapest for that plan). Returns {"early": BuildResult} when no package is possible at all."""
    early, prep = prepare_all(req, cat, inv)
    if early is not None:
        return {"early": early}
    assert prep is not None
    s, by_k, tr, _c0, _cand0 = prep
    kstar = preferred_city_count(req.nights, len(cat.cities_of(req.country)))
    rows = []
    for k, ctxs in by_k.items():
        for c in ctxs:
            cand = best_recommended(c, tr)
            fits = cand is not None
            if cand is None:
                cand = best_min_cost(c)
            if cand is None:
                continue
            it = finalize(c, cand, tr, extras=fits)
            total = int(it.metrics["total"])
            avg_nights = sum(n for _, n in c.plan) / k
            warnings = []
            if k > 1 and avg_nights < 3:
                warnings.append(f"RUSHED_PLAN: only {avg_nights:.1f} nights per city on average.")
            if not fits:
                warnings.append(f"OVER_BUDGET: the cheapest version of this plan is ₹{total - req.budget_inr} over your budget.")
            rows.append({
                "plan": _plan_dicts(c.plan), "cities": [x for x, _ in c.plan], "city_count": k,
                "total_inr": total, "fits_budget": fits, "budget_needed_inr": max(0, total - req.budget_inr),
                "transit_minutes": int(it.metrics["transit_minutes"]), "avg_hotel_stars": it.metrics["avg_hotel_stars"],
                "preferred": k == kstar, "warnings": warnings,
            })
    rows.sort(key=lambda r: (not r["fits_budget"], abs(r["city_count"] - kstar), r["transit_minutes"], r["total_inr"],
                             str(r["plan"])))
    return {"options": rows, "preferred_city_count": kstar}


def build_for_plan(req: TripRequest, cat, inv: Optional[Inventory], plan: Plan
                   ) -> Tuple[Optional[Itinerary], bool, Optional[str]]:
    """Build the package for ONE chosen city plan. Returns (itinerary, fits_budget, error_message)."""
    early, prep = prepare_all(req, cat, inv)
    if early is not None:
        return None, False, early.message
    assert prep is not None
    s, by_k, tr, _c0, _cand0 = prep
    ctx = next((c for c in by_k.get(len(plan), []) if c.plan == plan), None)
    if ctx is None:
        return None, False, ("That city plan is not possible for these dates, travelers and flights. "
                             "Pick one of the plans listed in the city-plan options.")
    cand = best_recommended(ctx, tr)
    fits = cand is not None
    if cand is None:
        cand = best_min_cost(ctx)
    if cand is None:
        return None, False, "No valid flights, hotels and transfers can be combined for that city plan."
    return finalize(ctx, cand, tr, extras=fits), fits, None
