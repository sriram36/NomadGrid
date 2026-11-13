"""Pocket city guides (S2) and nearby dining (S3). Read-only extras: never part of the price or the exported JSON."""
from fastapi import APIRouter, Request

from app.api.routes.shared import error

router = APIRouter()

_PRICE_NOTE = "Estimated out-of-pocket cost per person. Not included in your package total."


def _label(spot: dict) -> dict:
    return dict(spot, price_label=f"≈ ₹{spot['estimated_price_per_person_inr']:,} per person (estimate)")


@router.get("/cities/{city}/guide")
def city_guide(city: str, request: Request):
    guide = request.app.state.content.guide(city)
    if guide is None:
        return error(404, "CITY_NOT_FOUND", f"We have no guide for {city!r}.")
    return guide


@router.get("/cities/{city}/restaurants")
def city_restaurants(city: str, request: Request, area: str | None = None):
    spots = request.app.state.content.restaurants(city, area)
    if spots is None:
        return error(404, "CITY_NOT_FOUND", f"We have no dining suggestions for {city!r}" + (f" / {area!r}." if area else "."))
    return {"city": city, "area": area, "price_note": _PRICE_NOTE, "included_in_total": False,
            "restaurants": [_label(s) for s in spots]}


@router.get("/packages/{package_id}/guides")
def package_guides(package_id: str, request: Request):
    pkg = request.app.state.store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    content = request.app.state.content
    return {"guides": [g for g in (content.guide(l["city"]) for l in pkg["city_plan"]) if g is not None]}


@router.get("/packages/{package_id}/dining")
def package_dining(package_id: str, request: Request):
    """For every hotel stay in the holiday: 3-4 dining spots in that hotel's city and area."""
    pkg = request.app.state.store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    content = request.app.state.content
    stays = []
    for item in pkg["items"]:
        if item["type"] != "hotel":
            continue
        area = item["details"]["area"]
        spots = content.restaurants(item["city"], area) or content.restaurants(item["city"]) or []
        stays.append({"item_id": item["item_id"], "hotel": item["name"], "city": item["city"], "area": area,
                      "restaurants": [_label(s) for s in spots[:4]]})
    return {"stays": stays, "price_note": _PRICE_NOTE, "disclaimer": content.dining_disclaimer,
            "included_in_total": False}
