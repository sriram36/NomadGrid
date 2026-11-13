import hashlib
from datetime import date

from app.catalog.loader import Catalog, data_fingerprint
from app.config import DATA_DIR


def test_record_counts_match_data_dictionary(cat):
    assert len(cat.airports) == 10
    assert len(cat.flights) == 469
    assert len(cat.hotels) == 49
    assert len(cat.rooms) == 125
    assert len(cat.availability) == 2500
    assert len(cat.transfers) == 66
    assert len(cat.attractions) == 56


def test_departure_airport_lookup(cat):
    assert cat.departure_airport("Bengaluru") == "BLR"
    assert cat.departure_airport("Chennai") == "MAA"
    assert cat.departure_airport("Atlantis") is None


def test_country_lookup_is_exact(cat):
    assert cat.country("Japan")["code"] == "JP"
    assert cat.country("United Arab Emirates")["code"] == "AE"
    assert cat.country("japan") is None
    assert cat.country("Narnia") is None


def test_airports_serving_uses_serves_cities(cat):
    assert cat.airports_serving("Kyoto") == ["KIX"]          # Kyoto has no airport of its own
    assert cat.airports_serving("Tokyo") == ["HND", "NRT"]
    assert cat.airports_serving("Abu Dhabi") == ["AUH", "DXB"]
    assert "ITM" not in cat.airports_serving("Osaka")        # ITM serves nothing
    assert cat.airports_serving("Osaka") == ["KIX"]


def test_arrival_flights_match_on_arrival_local_date(cat):
    ids = {f["flight_id"] for f in cat.arrivals("BLR", "JP", date(2027, 4, 10))}
    assert ids == {"FL-401", "FL-405", "FL-740", "FL-403"}


def test_arrival_flights_can_depart_the_day_before(cat):
    f = cat.flights["FL-401"]
    assert f["departure_local"].startswith("2027-04-09")
    assert f["arrival_local"].startswith("2027-04-10")


def test_return_flights_match_on_departure_local_date(cat):
    ids = {f["flight_id"] for f in cat.returns("BLR", "JP", date(2027, 4, 16))}
    assert ids == {"FL-412", "FL-411"}


def test_rooms_left_and_default_zero_when_missing(cat):
    first = next(iter(cat.availability.items()))
    (room_id, d), left = first
    assert cat.rooms_left(room_id, d) == left
    assert cat.rooms_left("RM-NOPE", date(2027, 4, 10)) == 0
    assert cat.rooms_left(room_id, date(2030, 1, 1)) == 0


def test_airport_transfers_by_airport_and_city(cat):
    ids = {t["transfer_id"] for t in cat.airport_transfers("KIX", "Kyoto")}
    assert ids == {"TR-KIX-KYO-TAXI", "TR-KIX-KYO-BUS"}
    assert cat.airport_transfers("KIX", "Tokyo") == []


def test_link_transfers_between_cities(cat):
    assert [t["transfer_id"] for t in cat.link_transfers("Japan", "Tokyo", "Kyoto")] == ["TR-TYO-KYO-01"]
    assert [t["transfer_id"] for t in cat.link_transfers("United Arab Emirates", "Dubai", "Abu Dhabi")] == [
        "TR-DXB-AUH-BUS", "TR-DXB-AUH-TAXI"]
    assert cat.link_transfers("Japan", "Tokyo", "Dubai") == []


def test_hotels_and_rooms_by_city(cat):
    assert len(cat.hotels_in("Tokyo")) == 13
    assert len(cat.hotels_in("Abu Dhabi")) == 6
    rooms = cat.rooms_of("HTL-TYO-001")
    assert {r["room_id"] for r in rooms} == {"RM-TYO-001-A", "RM-TYO-001-B"}


def test_attractions_by_city_and_cities_of_country(cat):
    assert len(cat.attractions_in("Kyoto")) == 12
    assert cat.cities_of("Japan") == ["Tokyo", "Kyoto", "Osaka"]
    assert cat.country_of_airport("KIX") == "JP"


def test_loading_never_modifies_the_data_files():
    before = data_fingerprint(DATA_DIR)
    Catalog(DATA_DIR)
    after = data_fingerprint(DATA_DIR)
    assert before == after
    assert len(before) == 64 and int(before, 16) >= 0
