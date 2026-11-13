"""Plain data types shared by the engine."""
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class TripRequest:
    departure_city: str
    country: str
    start_date: date
    nights: int
    adults: int
    child_ages: Tuple[int, ...]
    budget_inr: int
    traveler_name: str = "Traveler"
    interests: Tuple[str, ...] = ()     # S1: optional interest tags (see app/interests.py)

    @property
    def children(self) -> int:
        return len(self.child_ages)

    @property
    def travelers(self) -> int:
        return self.adults + self.children

    @property
    def end_date(self) -> date:
        try:
            return self.start_date + timedelta(days=self.nights)
        except OverflowError:          # a start date at the very end of the calendar: far outside our window
            return date.max

    def to_dict(self) -> dict:
        return {
            "departure_city": self.departure_city, "country": self.country,
            "start_date": self.start_date.isoformat(), "nights": self.nights,
            "adults": self.adults, "child_ages": list(self.child_ages),
            "budget_inr": self.budget_inr, "traveler_name": self.traveler_name, "interests": list(self.interests),
        }


@dataclass
class Leg:
    city: str
    nights: int
    check_in: date
    check_out: date
    hotel: dict
    room: dict
    rooms: int
    price: int
    pinned: bool = False


@dataclass
class TransferUse:
    rec: dict
    pickup: datetime
    arrive: datetime
    price: int
    quantity: int
    day: date
    from_city: Optional[str] = None
    to_city: Optional[str] = None


@dataclass
class Visit:
    attraction: dict
    start: datetime
    end: datetime
    price: int
    day: date
    pinned: bool = False


@dataclass
class Itinerary:
    request: TripRequest
    legs: List[Leg]
    arr_flight: dict
    ret_flight: dict
    arr_transfer: TransferUse
    dep_transfer: TransferUse
    links: List[TransferUse]
    visits: List[Visit]
    metrics: Dict[str, Any] = field(default_factory=dict)
    arr_pinned: bool = False
    ret_pinned: bool = False

    @property
    def cities(self) -> List[str]:
        return [l.city for l in self.legs]
