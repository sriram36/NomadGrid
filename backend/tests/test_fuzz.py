"""Seeded fuzz: random requests across the whole input space. Every PACKAGE must pass the validator."""
import collections
import random
import time
from datetime import date, timedelta

import pytest

from app.engine.builder import build
from app.engine.models import TripRequest
from app.export.package import to_package, to_trip_format
from app.validator.validate import validate_trip

KNOWN_REASONS = {"OUT_OF_WINDOW", "NO_ARRIVAL_FLIGHT", "INSUFFICIENT_SEATS_ARRIVAL", "NO_RETURN_FLIGHT",
                 "INSUFFICIENT_SEATS_RETURN", "NO_CITY_PLAN_FOR_FLIGHTS", "NO_ROOMS", "NO_AIRPORT_TRANSFER",
                 "NO_CITY_TRANSFER", "NOT_ENOUGH_ATTRACTIONS"}


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_fuzz_every_package_is_valid_and_within_budget(cat, seed):
    rnd = random.Random(seed)
    deps = [d["city"] for d in cat.departure_cities()]
    countries = [c["name"] for c in cat.destinations["countries"]]
    outcomes = collections.Counter()
    for _ in range(220):
        nights = rnd.randint(3, 10)
        start = date(2027, 4, 1) + timedelta(days=rnd.randint(0, 19 - nights + 1))
        adults = rnd.choice([1, 1, 2, 2, 2, 3, 4])
        kids = tuple(rnd.choice([[], [], [5], [6, 9], [2, 4, 11], [16], [0]]))
        budget = rnd.choice([80000, 150000, 250000, 350000, 400000, 600000, 1000000])
        req = TripRequest(rnd.choice(deps), rnd.choice(countries), start, nights, adults, kids, budget)
        t = time.time()
        res = build(req, cat)
        assert time.time() - t < 5, f"too slow: {req}"
        outcomes[res.outcome] += 1
        if res.outcome == "PACKAGE":
            pkg = to_package(res.itinerary, cat, "pkg_f", {"name": "x", "home_airport": cat.departure_airport(req.departure_city),
                                                           "adults": adults, "children": len(kids), "child_ages": list(kids)})
            v = validate_trip(to_trip_format(pkg), cat, first_package=True)
            assert v == [], (req, [x.to_dict() for x in v][:3])
            assert pkg["pricing"]["total_inr"] <= budget, req
        elif res.outcome == "OVER_BUDGET":
            assert res.cheapest_total > budget, req
        else:
            assert res.reason_code in KNOWN_REASONS and res.message, req
    assert outcomes["PACKAGE"] > 20, outcomes        # a sudden collapse in packages means a regression
