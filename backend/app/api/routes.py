"""HTTP routes. Thin layer: parse -> engine/store -> shape the response."""
import re
import secrets

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.requests import parse_request
from app.changes.service import (
    apply_change, attraction_options_for, flight_options_for, hotel_options_for, request_from_package,
)
from app.engine.alternatives import find_alternatives, inr
from app.engine.builder import build
from app.engine.variants import build_variants, plan_options
from app.export.package import to_package, to_trip_format
from app.quickparse.parser import parse_quick_request
from app.store.db import InventoryConflict
from app.validator.validate import validate_trip

router = APIRouter(prefix="/api")


def error(status: int, code: str, message: str, **extra):
    body = {"error": {"code": code, "message": message, **extra}}
    return JSONResponse(status_code=status, content=body)


def _traveler(req, cat) -> dict:
    return {"name": req.traveler_name, "home_airport": cat.departure_airport(req.departure_city),
            "departure_city": req.departure_city,
            "adults": req.adults, "children": req.children, "child_ages": list(req.child_ages)}


def _new_id() -> str:
    return "pkg_" + secrets.token_hex(6)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/meta")
def meta(request: Request):
    cat = request.app.state.cat
    r = cat.rules
    return {
        "departure_cities": cat.departure_cities(),
        "countries": [{"name": c["name"], "code": c["code"], "cities": [x["name"] for x in c["cities"]]}
                      for c in cat.destinations["countries"]],
        "rules": {"min_nights": r["min_nights"], "max_nights": r["max_nights"],
                  "first_night": r["data_window"]["first_night"], "last_departure": r["data_window"]["last_departure"],
                  "child_age_max": 17},
    }


async def _read_trip_request(request: Request):
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
        pkg = to_package(alt.result.itinerary, cat, _new_id(), _traveler(alt.request, cat), variant="ALTERNATIVE")
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
    req, failure = await _read_trip_request(request)
    if failure is not None or req is None:
        return failure
    inv = request.app.state.inventory()
    res = build(req, cat, inv)

    if res.outcome == "PACKAGE":
        assert res.itinerary is not None
        pkg = to_package(res.itinerary, cat, _new_id(), _traveler(req, cat))
        store.save_package(pkg)
        return {"outcome": "PACKAGE", "package": pkg}
    if res.outcome == "OVER_BUDGET":
        return _over_budget_response(req, res, cat, store, inv)
    return {"outcome": "NO_PACKAGE", "reason_code": res.reason_code, "message": res.message, "details": res.details}


@router.post("/packages/variants")
async def build_three_packages(request: Request):
    """G4: the cheapest, the fastest and the best-rated package (plus the recommended one). The traveler picks one."""
    cat, store = request.app.state.cat, request.app.state.store
    req, failure = await _read_trip_request(request)
    if failure is not None or req is None:
        return failure
    inv = request.app.state.inventory()
    out = build_variants(req, cat, inv)
    if "early" in out:
        res = out["early"]
        if res.outcome == "OVER_BUDGET":
            return _over_budget_response(req, res, cat, store, inv)
        return {"outcome": "NO_PACKAGE", "reason_code": res.reason_code, "message": res.message, "details": res.details}
    traveler = _traveler(req, cat)
    packages = {}
    for name, itinerary in out["variants"].items():
        if itinerary is None:
            packages[name] = None
            continue
        pkg = to_package(itinerary, cat, _new_id(), traveler, variant=name.upper())
        store.save_package(pkg)
        packages[name] = pkg
    default = build(req, cat, inv)
    recommended = None
    if default.outcome == "PACKAGE" and default.itinerary is not None:
        recommended = to_package(default.itinerary, cat, _new_id(), traveler, variant="RECOMMENDED")
        store.save_package(recommended)
    return {"outcome": "VARIANTS", "recommended": recommended, "variants": packages, "notes": out["notes"]}


@router.post("/parse-request")
async def parse_request_text(request: Request):
    """S1: read a short sentence with fixed rules (no AI) and fill the form fields."""
    try:
        body = await request.json()
    except Exception:
        body = None
    text = body.get("text") if isinstance(body, dict) else None
    if not isinstance(text, str) or not text.strip() or len(text) > 1000:
        return error(422, "VALIDATION_ERROR", "Type a short request, for example “Japan 10 Apr 6 nights 2 adults "
                     "1 child 6 from Bengaluru 3.5 lakh”.",
                     fields=[{"field": "text", "message": "Enter between 1 and 1000 characters of text."}])
    return parse_quick_request(text)


@router.get("/packages/{package_id}")
def get_package(package_id: str, request: Request):
    pkg = request.app.state.store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    return pkg


@router.post("/packages/{package_id}/changes")
async def change_package(package_id: str, request: Request):
    cat, store = request.app.state.cat, request.app.state.store
    pkg = store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    try:
        op = await request.json()
    except Exception:
        return error(422, "VALIDATION_ERROR", "The request body must be valid JSON.")
    if not isinstance(op, dict):
        return error(422, "VALIDATION_ERROR", "The change must be a JSON object with an 'op' field.")
    res = apply_change(pkg, op, cat, request.app.state.inventory())
    if res["result"] == "APPLIED":
        store.save_package(res["package"], keep_history=True)
        res["undo_available"] = True
    return res


@router.post("/packages/{package_id}/undo")
def undo_last_change(package_id: str, request: Request):
    store = request.app.state.store
    pkg = store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    if pkg["status"] == "BOOKED":
        return {"result": "REFUSED", "reason_code": "PACKAGE_LOCKED",
                "reason": "This holiday is already booked, so it can't be changed or undone."}
    restored = store.undo(package_id)
    if restored is None:
        return {"result": "REFUSED", "reason_code": "NOTHING_TO_UNDO", "reason": "There is no change to undo."}
    return {"result": "UNDONE", "package": restored, "summary": "Your last change was undone.",
            "undo_available": store.history_count(package_id) > 0}


@router.get("/packages/{package_id}/options/hotels")
def hotel_options(package_id: str, city: str, request: Request):
    pkg = request.app.state.store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    if city not in [l["city"] for l in pkg["city_plan"]]:
        return error(422, "VALIDATION_ERROR", f"{city!r} is not one of the cities in this holiday.")
    return {"city": city, "options": hotel_options_for(pkg, city, request.app.state.cat, request.app.state.inventory())}


@router.get("/packages/{package_id}/options/flights")
def flight_options(package_id: str, leg: str, request: Request):
    pkg = request.app.state.store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    if leg not in ("ARRIVAL", "RETURN"):
        return error(422, "VALIDATION_ERROR", "leg must be ARRIVAL or RETURN.")
    return {"leg": leg, "options": flight_options_for(pkg, leg, request.app.state.cat, request.app.state.inventory())}


@router.get("/packages/{package_id}/options/attractions")
def attraction_options(package_id: str, date: str, request: Request):
    pkg = request.app.state.store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    out = attraction_options_for(pkg, date, request.app.state.cat, request.app.state.inventory())
    if out.get("error"):
        return error(422, "VALIDATION_ERROR", "Choose a day from the trip (the last day is for going home).")
    return out


@router.get("/packages/{package_id}/options/city-plans")
def city_plan_options(package_id: str, request: Request):
    """G3: every valid city plan with the total it would give, to compare and choose from."""
    pkg = request.app.state.store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    out = plan_options(request_from_package(pkg), request.app.state.cat, request.app.state.inventory())
    if "early" in out:
        return {"options": [], "message": out["early"].message}
    current = [(l["city"], l["nights"]) for l in pkg["city_plan"]]
    for row in out["options"]:
        row["current"] = [(p["city"], p["nights"]) for p in row["plan"]] == current
        row["price_delta_inr"] = row["total_inr"] - pkg["pricing"]["total_inr"]
    return out


@router.get("/packages/{package_id}/export")
def export_package(package_id: str, request: Request):
    pkg = request.app.state.store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    return JSONResponse(content=to_trip_format(pkg), headers={
        "Content-Disposition": f'attachment; filename="nomadgrid-trip-{package_id}.json"'})


@router.post("/packages/{package_id}/confirm")
def confirm_package(package_id: str, request: Request):
    cat, store = request.app.state.cat, request.app.state.store
    pkg = store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    existing = store.reservation_for_package(package_id)
    if existing:
        return {"reservation_number": existing[0], "package": existing[1]}
    violations = validate_trip(to_trip_format(pkg), cat)
    if violations:
        return error(409, "PACKAGE_INVALID", "This package no longer passes every travel rule, so it can't be booked.",
                     violations=[v.to_dict() for v in violations])

    def make_booked(p: dict, number: str, when: str) -> dict:
        booked = dict(p)
        booked["status"] = "BOOKED"
        booked["reservation"] = {"number": number, "confirmed_at": when}
        booked["items"] = [dict(i, status="BOOKED", booking={"reference": number}) for i in p["items"]]
        return booked

    try:
        out = store.confirm(package_id, make_booked, cat)
    except InventoryConflict as e:
        return error(409, "INVENTORY_CONFLICT", e.message + " Please choose another flight or hotel.")
    if out is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    number, booked = out
    return {"reservation_number": number, "package": booked}


@router.get("/reservations/{number:path}")
def get_reservation(number: str, request: Request):
    not_found = error(404, "RESERVATION_NOT_FOUND", "Reservation not found. Check the 10-digit number and try again.")
    if not re.fullmatch(r"[0-9]{10}", number):
        return not_found
    pkg = request.app.state.store.get_reservation(number)
    return pkg if pkg is not None else not_found
