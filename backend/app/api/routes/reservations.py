"""Look a booking up by its 10-digit reservation number."""
import re

from fastapi import APIRouter, Request

from app.api.routes.shared import error

router = APIRouter()


@router.get("/reservations/{number:path}")
def get_reservation(number: str, request: Request):
    not_found = error(404, "RESERVATION_NOT_FOUND", "Reservation not found. Check the 10-digit number and try again.")
    if not re.fullmatch(r"[0-9]{10}", number):
        return not_found
    pkg = request.app.state.store.get_reservation(number)
    return pkg if pkg is not None else not_found
