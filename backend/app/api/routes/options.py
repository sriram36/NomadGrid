"""The choices behind each Change button, with price differences."""
from fastapi import APIRouter, Request

from app.api.routes.shared import error
from app.changes.rebuild import request_from_package
from app.changes.service import attraction_options_for, flight_options_for, hotel_options_for
from app.engine.variants import plan_options

router = APIRouter()


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
