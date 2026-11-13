"""Small helpers every route module uses."""
import secrets

from fastapi.responses import JSONResponse


def error(status: int, code: str, message: str, **extra):
    body = {"error": {"code": code, "message": message, **extra}}
    return JSONResponse(status_code=status, content=body)


def traveler_of(req, cat) -> dict:
    return {"name": req.traveler_name, "home_airport": cat.departure_airport(req.departure_city),
            "departure_city": req.departure_city,
            "adults": req.adults, "children": req.children, "child_ages": list(req.child_ages)}


def new_id() -> str:
    return "pkg_" + secrets.token_hex(6)
