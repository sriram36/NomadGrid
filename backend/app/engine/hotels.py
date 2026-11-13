"""Hotel + room options for one city stay."""
from datetime import date, timedelta
from typing import List, Optional, Tuple

from app.core.pricing import hotel_price, rooms_needed


def stay_points_per_night(hotel: dict, children: int) -> float:
    """Stay quality for one night, 0..40 (see PRD 6.10A): stars 28 + family fit 6 + guest rating 6."""
    stars = 28.0 * (hotel["stars"] - 2) / 3.0
    family = 6.0 if (children == 0 or hotel.get("family_friendly")) else 0.0
    rating = 6.0 * min(max((hotel["rating"] - 6.9) / 2.5, 0.0), 1.0)
    return stars + family + rating


def hotel_options(cat, inv, city: str, check_in: date, nights: int,
                  adults: int, children: int, stats: Optional[dict] = None) -> List[dict]:
    """Every (hotel, room type) in `city` that fits the party and has rooms on every night.

    `stats` (optional) collects why options were dropped, for failure messages.
    """
    out = []
    stats = stats if stats is not None else {}
    stats.setdefault("considered", 0)
    stats.setdefault("no_fit", 0)
    stats.setdefault("sold_out", 0)
    nights_dates = [check_in + timedelta(days=i) for i in range(nights)]
    for hotel in cat.hotels_in(city):
        for room in cat.rooms_of(hotel["hotel_id"]):
            stats["considered"] += 1
            k = rooms_needed(room, adults, children)
            if k is None:
                stats["no_fit"] += 1
                continue
            if any(inv.rooms_left(room["room_id"], d) < k for d in nights_dates):
                stats["sold_out"] += 1
                continue
            out.append({
                "hotel": hotel, "room": room, "rooms": k, "nights": nights,
                "price": hotel_price(room, k, nights),
                "sp": stay_points_per_night(hotel, children),
                "area": hotel["area"],
            })
    out.sort(key=lambda o: (o["price"], o["hotel"]["hotel_id"], o["room"]["room_id"]))
    return out


def pareto(options: List[dict], by_area: bool) -> List[dict]:
    """Keep options not dominated on (price lower, stay points higher).

    When `by_area` is set (first/last city, whose airport transfer depends on the hotel's area)
    the frontier is computed per area, so a pricier hotel in an area with a cheaper transfer survives.
    """
    groups = {}
    for o in options:
        groups.setdefault(o["area"] if by_area else None, []).append(o)
    kept = []
    for g in groups.values():
        g.sort(key=lambda o: (o["price"], -o["sp"], o["hotel"]["hotel_id"], o["room"]["room_id"]))
        best = -1.0
        for o in g:
            if o["sp"] > best + 1e-9:
                kept.append(o)
                best = o["sp"]
    kept.sort(key=lambda o: (o["price"], o["hotel"]["hotel_id"], o["room"]["room_id"]))
    return kept
