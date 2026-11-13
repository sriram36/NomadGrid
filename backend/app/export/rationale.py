"""S3 own idea: "Why this plan" — a plain-language explanation attached to every package.

Every sentence is derived from the actual itinerary (nothing is canned), so the traveler can see why the
app chose these cities, flights and hotels, and what they would be giving up by changing them.
"""
from app.engine.alternatives import inr
from app.engine.cityplan import preferred_city_count
from app.engine.models import Itinerary
from app.export.package import time_label


def _hm(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60:02d}m"


def build_rationale(it: Itinerary, cat, total: int) -> dict:
    req = it.request
    k = len(it.legs)
    kstar = preferred_city_count(req.nights, len(cat.cities_of(req.country)))
    plan = " → ".join(f"{l.city} ({l.nights} nights)" for l in it.legs)
    reasons = []

    if k == kstar:
        word = "city" if k == 1 else "cities"
        reasons.append(f"{req.nights} nights suits {k} {word} — about one city per 3 nights, so you are not rushing around.")
    else:
        reasons.append(f"{req.nights} nights would normally suit {kstar} city(ies), but a {k}-city plan fits your budget, "
                       f"flights and rooms best.")

    transit = it.metrics.get("transit_minutes")
    if transit is None:
        transit = (it.arr_flight["duration_minutes"] + it.ret_flight["duration_minutes"]
                   + sum(l.rec["duration_minutes"] for l in it.links))
    hop = ""
    if it.links:
        hop = " including " + ", ".join(f"{l.from_city} → {l.to_city} ({_hm(l.rec['duration_minutes'])})" for l in it.links)
    reasons.append(f"Flights and city-to-city travel add up to {_hm(int(transit))}{hop}.")

    direct = [f for f in (it.arr_flight, it.ret_flight) if f["stops"] == 0]
    stops = ("both flights are direct" if len(direct) == 2 else
             "one flight is direct and one has a stop" if direct else "both flights have a stop")
    landing = it.arr_flight["_arr"]
    ready = it.arr_transfer.arrive
    after = f"; you are at your hotel around {time_label(ready)}" if ready.date() == landing.date() else ""
    reasons.append(f"You land at {time_label(landing)} on day 1 ({stops}){after}.")

    stars = sum(l.hotel["stars"] * l.nights for l in it.legs) / req.nights
    fam = all(l.hotel.get("family_friendly") for l in it.legs)
    hotels = ", ".join(f"{l.hotel['name']} in {l.city}" for l in it.legs)
    reasons.append(f"Hotels average {stars:.1f}★ ({hotels})" + (" and are all family friendly." if fam else "."))

    pct = round(100 * total / req.budget_inr)
    left = req.budget_inr - total
    reasons.append(f"The holiday costs ₹{inr(total)} of your ₹{inr(req.budget_inr)} budget ({pct}%)"
                   + (f", leaving ₹{inr(left)}." if left >= 0 else f" — ₹{inr(-left)} over."))

    if it.visits:
        cats = sorted({v.attraction["category"].replace("_", " ").lower() for v in it.visits})
        reasons.append(f"{len(it.visits)} sight(s) planned across {len({v.day for v in it.visits})} day(s) — a mix of "
                       f"{', '.join(cats[:4])}.")

    picks = [f"your hotel in {l.city}" for l in it.legs if l.pinned]
    picks += [f"your {t} flight" for t, p in (("arrival", it.arr_pinned), ("return", it.ret_pinned)) if p]
    picks += [v.attraction["name"] for v in it.visits if v.pinned]
    if picks:
        reasons.append("Kept exactly as you chose: " + ", ".join(picks) + ".")

    return {"headline": plan, "reasons": reasons,
            "alternatives_hint": "Curious about a different mix of cities? Open the city-plan options to compare each "
                                 "plan's price and travel time."}
