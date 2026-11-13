"""Read, export and confirm (book) a package."""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.api.routes.shared import error
from app.export.package import to_trip_format
from app.store.db import InventoryConflict
from app.validator.validate import validate_trip

router = APIRouter()


@router.get("/packages/{package_id}")
def get_package(package_id: str, request: Request):
    pkg = request.app.state.store.get_package(package_id)
    if pkg is None:
        return error(404, "PACKAGE_NOT_FOUND", "We couldn't find that package.")
    return pkg


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
