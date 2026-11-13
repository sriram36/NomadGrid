import pytest

from app.core.pricing import (
    attraction_price, flight_price, hotel_price, rooms_needed, transfer_price, vehicles,
)


def room(ma, mc):
    return {"max_adults": ma, "max_children": mc}


def inr(x):
    return {"amount": x, "currency": "INR"}


# ---------- room fit ----------
@pytest.mark.parametrize("ma,mc,adults,children,expected", [
    (2, 0, 2, 1, 2),      # TWIN: 2 adults + 1 child need 2 rooms
    (2, 2, 2, 1, 1),      # FAMILY fits in 1
    (1, 0, 2, 1, None),   # SINGLE can never fit 2 adults + child (k=3 > adults)
    (1, 0, 1, 0, 1),      # SINGLE for a solo adult
    (4, 2, 3, 3, 1),      # FAMILY_SUITE
    (3, 0, 2, 1, 1),      # TRIPLE
    (2, 0, 4, 0, 2),      # four adults in TWINs
    (2, 0, 1, 1, 1),      # one adult + one child in a TWIN
    (2, 0, 1, 2, None),   # one adult + two kids: needs 2 rooms but only 1 adult
    (2, 2, 1, 3, 1),      # FAMILY: 1 adult + 3 kids = 4 <= 4
    (2, 2, 1, 4, None),   # 5 people, 1 adult: k=2 > adults
])
def test_rooms_needed(ma, mc, adults, children, expected):
    assert rooms_needed(room(ma, mc), adults, children) == expected


def test_rooms_needed_satisfies_all_three_inequalities():
    for ma, mc in [(1, 0), (2, 0), (2, 2), (3, 0), (4, 2)]:
        for adults in range(1, 7):
            for children in range(0, 6):
                k = rooms_needed(room(ma, mc), adults, children)
                if k is None:
                    continue
                assert adults <= k * ma
                assert adults + children <= k * (ma + mc)
                assert adults >= k
                # minimal: k-1 rooms would not fit
                if k > 1:
                    km = k - 1
                    assert not (adults <= km * ma and adults + children <= km * (ma + mc))


# ---------- vehicles ----------
@pytest.mark.parametrize("travelers,cap,expected", [(3, 4, 1), (4, 4, 1), (5, 4, 2), (9, 4, 3), (9, 8, 2), (12, 99, 1)])
def test_vehicles(travelers, cap, expected):
    assert vehicles(travelers, cap) == expected


# ---------- prices ----------
def test_flight_price_charges_children_full_seat():
    assert flight_price({"price_per_seat": inr(25200)}, travelers=3) == 75600


def test_hotel_price_is_rate_times_rooms_times_nights():
    assert hotel_price({"price_per_night": inr(8120)}, rooms=2, nights=3) == 48720


def test_transfer_per_person_uses_child_price():
    t = {"pricing": "PER_PERSON", "price": inr(1792), "child_price": inr(896), "max_passengers": 99}
    assert transfer_price(t, adults=2, children=1) == 2 * 1792 + 896


def test_transfer_per_person_without_child_price_charges_adult_price():
    t = {"pricing": "PER_PERSON", "price": inr(500), "max_passengers": 99}
    assert transfer_price(t, adults=2, children=1) == 1500


def test_transfer_per_vehicle_rounds_up_vehicles():
    t = {"pricing": "PER_VEHICLE", "price": inr(13440), "max_passengers": 4}
    assert transfer_price(t, adults=2, children=1) == 13440
    assert transfer_price(t, adults=3, children=2) == 2 * 13440


def test_attraction_price_child_price_zero_is_free_not_missing():
    a = {"price_per_person": inr(336), "child_price": inr(0)}
    assert attraction_price(a, adults=2, children=1) == 672


def test_attraction_price_missing_child_price_uses_adult_price():
    a = {"price_per_person": inr(572)}
    assert attraction_price(a, adults=2, children=1) == 3 * 572


def test_attraction_price_free_attraction():
    a = {"price_per_person": inr(0)}
    assert attraction_price(a, adults=2, children=3) == 0
