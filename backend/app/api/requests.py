"""Validation of the trip request (M1). Returns per-field, human-readable errors."""
import re
from datetime import date
from typing import List, Optional, Tuple

from app.engine.models import TripRequest

MAX_ADULTS = 20
MAX_CHILDREN = 20
MAX_BUDGET = 10 ** 9


def _whole(x) -> Optional[int]:
    """Whole number from an int or an integral float; never from bool/str."""
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, float) and x.is_integer():
        return int(x)
    return None


def parse_request(raw, cat) -> Tuple[Optional[TripRequest], List[dict]]:
    if not isinstance(raw, dict):
        return None, [{"field": "body", "message": "The request must be a JSON object."}]
    errors: List[dict] = []

    def err(field, msg):
        errors.append({"field": field, "message": msg})

    dep = raw.get("departure_city")
    cities = [d["city"] for d in cat.departure_cities()]
    if not isinstance(dep, str) or cat.departure_airport(dep) is None:
        err("departure_city", f"Choose a departure city from the list: {', '.join(cities)}.")

    country = raw.get("country")
    countries = [c["name"] for c in cat.destinations["countries"]]
    if not isinstance(country, str) or cat.country(country) is None:
        err("country", f"Choose a destination country from the list: {', '.join(countries)}.")

    start = None
    sd = raw.get("start_date")
    if isinstance(sd, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", sd):
        try:
            start = date.fromisoformat(sd)
        except ValueError:
            start = None
    if start is None:
        err("start_date", "Enter the first day of the holiday as a real date (YYYY-MM-DD).")

    rules = cat.rules
    nights = _whole(raw.get("nights"))
    if nights is None or not rules["min_nights"] <= nights <= rules["max_nights"]:
        err("nights", f"Nights must be a whole number between {rules['min_nights']} and {rules['max_nights']}.")

    adults = _whole(raw.get("adults"))
    if adults is None or not 1 <= adults <= MAX_ADULTS:
        err("adults", f"Adults must be a whole number between 1 and {MAX_ADULTS}.")

    ages_raw = raw.get("child_ages", [])
    ages: List[int] = []
    if not isinstance(ages_raw, list) or len(ages_raw) > MAX_CHILDREN:
        err("child_ages", f"Children's ages must be a list of up to {MAX_CHILDREN} ages.")
    else:
        for i, a in enumerate(ages_raw, start=1):
            n = _whole(a)
            if n is None or not 0 <= n <= 17:
                err("child_ages", f"Child {i}: age must be a whole number between 0 and 17.")
            else:
                ages.append(n)

    budget = _whole(raw.get("budget_inr"))
    if budget is None or not 1 <= budget <= MAX_BUDGET:
        err("budget_inr", "Budget must be a positive whole number of rupees.")

    name = raw.get("traveler_name", "Traveler")
    if name is None or name == "":
        name = "Traveler"
    if not isinstance(name, str) or len(name.strip()) > 60:
        err("traveler_name", "Name must be text of at most 60 characters.")
        name = "Traveler"

    if (errors or not isinstance(dep, str) or not isinstance(country, str) or start is None or nights is None
            or adults is None or budget is None):
        return None, errors
    return TripRequest(dep, country, start, nights, adults, tuple(ages), budget, name.strip() or "Traveler"), []
