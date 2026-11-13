"""What a build returns, and how a failed build explains itself."""
from dataclasses import dataclass, field
from typing import List, Optional

from app.engine.models import Itinerary

STAGES = ["OUT_OF_WINDOW", "NO_ARRIVAL_FLIGHT", "INSUFFICIENT_SEATS_ARRIVAL", "NO_RETURN_FLIGHT",
          "INSUFFICIENT_SEATS_RETURN", "NO_CITY_PLAN_FOR_FLIGHTS", "NO_ROOMS", "NO_AIRPORT_TRANSFER",
          "NO_CITY_TRANSFER", "NOT_ENOUGH_ATTRACTIONS"]


@dataclass
class BuildResult:
    outcome: str                       # PACKAGE | OVER_BUDGET | NO_PACKAGE
    itinerary: Optional[Itinerary] = None
    cheapest_total: Optional[int] = None
    reason_code: Optional[str] = None
    message: Optional[str] = None
    details: List[str] = field(default_factory=list)


class Diag:
    """Remembers the furthest stage any candidate reached; that explains a NO_PACKAGE."""

    def __init__(self):
        self.idx, self.code, self.message = -1, None, None

    def fail(self, code: str, message: str):
        i = STAGES.index(code)
        if i > self.idx:
            self.idx, self.code, self.message = i, code, message
