"""Build a holiday: one recommended package, or the recommended / cheapest / best-rated choices; over-budget answers."""
from fastapi import APIRouter, Request

from app.api.requests import parse_request
from app.api.routes.shared import error, new_id, traveler_of
from app.engine.alternatives import find_alternatives, inr
from app.engine.builder import build
from app.engine.variants import build_variants
from app.export.package import to_package

router = APIRouter()


async def read_trip_request(request: Request):
    """Parse and validate the 7-field trip request. Returns (TripRequest, None) or (None, error response)."""
    try:
        raw = await request.json()
    except Exception:
        return None, error(422, "VALIDATION_ERROR", "The request body must be valid JSON.",
                           fields=[{"field": "body", "message": "The request body must be valid JSON."}])
    req, errors = parse_request(raw, request.app.state.cat)
    if errors or req is None:
        return None, error(422, "VALIDATION_ERROR", "Please fix the highlighted fields.", fields=errors)
    return req, None


def _over_budget_response(req, res, cat, store, inv) -> dict:
    """M8: say the trip is not possible as asked, show the cheapest total, and offer what IS possible."""
    assert res.cheapest_total is not None
    over = res.cheapest_total - req.budget_inr
    alts = []
    for i, alt in enumerate(find_alternatives(req, cat, inv), start=1):
        assert alt.result.itinerary is not None
        pkg = to_package(alt.result.itinerary, cat, new_id(), traveler_of(alt.request, cat), variant="ALTERNATIVE")
        store.save_package(pkg)
        alts.append({"id": f"alt{i}", "levers": alt.levers, "label": alt.label, "changes": alt.changes,
                     "total_inr": pkg["pricing"]["total_inr"], "remaining_inr": pkg["pricing"]["remaining_inr"],
                     "package_id": pkg["package_id"]})
    return {
        "outcome": "OVER_BUDGET", "cheapest_total_inr": res.cheapest_total, "over_by_inr": over,
        "message": (f"This trip is not possible within ₹{inr(req.budget_inr)} as requested. "
                    f"The cheapest version costs ₹{inr(res.cheapest_total)} (₹{inr(over)} over your budget)."),
        "alternatives": alts,
        "raise_budget": {"budget_inr": res.cheapest_total, "extra_needed_inr": over,
                         "label": f"Increase budget to ₹{inr(res.cheapest_total)} (+₹{inr(over)}) "
                                  f"and keep your original request"},
    }


@router.post("/packages")
async def build_package(request: Request):
    cat, store = request.app.state.cat, request.app.state.store
    req, failure = await read_trip_request(request)
    if failure is not None or req is None:
        return failure
    inv = request.app.state.inventory()
    res = build(req, cat, inv)

    if res.outcome == "PACKAGE":
        assert res.itinerary is not None
        pkg = to_package(res.itinerary, cat, new_id(), traveler_of(req, cat))
        store.save_package(pkg)
        return {"outcome": "PACKAGE", "package": pkg}
    if res.outcome == "OVER_BUDGET":
        return _over_budget_response(req, res, cat, store, inv)
    return {"outcome": "NO_PACKAGE", "reason_code": res.reason_code, "message": res.message, "details": res.details}


@router.post("/packages/variants")
async def build_three_packages(request: Request):
    """G4: the cheapest and the best-rated package (plus the recommended one). The traveler picks one."""
    cat, store = request.app.state.cat, request.app.state.store
    req, failure = await read_trip_request(request)
    if failure is not None or req is None:
        return failure
    inv = request.app.state.inventory()
    out = build_variants(req, cat, inv)
    if "early" in out:
        res = out["early"]
        if res.outcome == "OVER_BUDGET":
            return _over_budget_response(req, res, cat, store, inv)
        return {"outcome": "NO_PACKAGE", "reason_code": res.reason_code, "message": res.message, "details": res.details}
    traveler = traveler_of(req, cat)
    packages = {}
    for name, itinerary in out["variants"].items():
        if itinerary is None:
            packages[name] = None
            continue
        pkg = to_package(itinerary, cat, new_id(), traveler, variant=name.upper())
        store.save_package(pkg)
        packages[name] = pkg
    default = build(req, cat, inv)
    recommended = None
    if default.outcome == "PACKAGE" and default.itinerary is not None:
        recommended = to_package(default.itinerary, cat, new_id(), traveler, variant="RECOMMENDED")
        store.save_package(recommended)
    return {"outcome": "VARIANTS", "recommended": recommended, "variants": packages, "notes": out["notes"]}
