"""Price formulas and room-fit rule (problem statement section 4). All prices are whole INR."""
from math import ceil
from typing import Optional


def _amt(x) -> int:
    return int(x["amount"])


def flight_price(flight: dict, travelers: int) -> int:
    return _amt(flight["price_per_seat"]) * travelers


def hotel_price(room: dict, rooms: int, nights: int) -> int:
    return _amt(room["price_per_night"]) * rooms * nights


def vehicles(travelers: int, max_passengers: int) -> int:
    return ceil(travelers / max_passengers)


def transfer_price(transfer: dict, adults: int, children: int) -> int:
    price = _amt(transfer["price"])
    if transfer["pricing"] == "PER_VEHICLE":
        return price * vehicles(adults + children, transfer["max_passengers"])
    child = _amt(transfer["child_price"]) if "child_price" in transfer else price
    return adults * price + children * child


def transfer_quantity(transfer: dict, adults: int, children: int) -> int:
    """Export quantity: vehicles for PER_VEHICLE, travelers for PER_PERSON."""
    if transfer["pricing"] == "PER_VEHICLE":
        return vehicles(adults + children, transfer["max_passengers"])
    return adults + children


def attraction_price(attraction: dict, adults: int, children: int) -> int:
    price = _amt(attraction["price_per_person"])
    # child_price == 0 is a real (free) price; only an ABSENT field falls back to the adult price.
    child = _amt(attraction["child_price"]) if "child_price" in attraction else price
    return adults * price + children * child


def rooms_needed(room: dict, adults: int, children: int) -> Optional[int]:
    """Smallest k rooms of this type that fit the party, or None if no k works.

    k rooms fit if adults <= k*max_adults, adults+children <= k*(max_adults+max_children)
    and adults >= k.
    """
    ma, mc = room["max_adults"], room["max_children"]
    if ma <= 0 or adults < 1:
        return None
    k = max(1, ceil(adults / ma), ceil((adults + children) / (ma + mc)))
    return k if adults >= k else None
