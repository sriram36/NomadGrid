"""Service info for the form, and the quick-request reader."""
from fastapi import APIRouter, Request

from app.api.routes.shared import error
from app.interests import tag_list
from app.quickparse.parser import parse_quick_request

router = APIRouter()


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
        "interests": tag_list(),
    }


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
