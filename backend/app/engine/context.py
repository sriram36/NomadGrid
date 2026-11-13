"""Working data for the builder: per-plan candidates (PlanCtx) and the per-request search session."""
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from app.config import DAY_END_MIN, DAY_START_MIN, SETTLE_MIN, WINDOW_FIRST, WINDOW_LAST
from app.core.pricing import transfer_price, transfer_quantity
from app.core.timeutil import tod
from app.engine import attractions as attr
from app.engine.airport import best_airport_transfer
from app.engine.cityplan import Plan
from app.engine.hotels import hotel_options, pareto
from app.engine.inventory import Inventory
from app.engine.models import TripRequest
from app.engine.schedule import arrival_pickup, departure_pickup, intercity_departure
from app.engine.results import BuildResult, Diag


class PlanCtx:
    def __init__(self, s: "Session", plan: Plan):
        self.s, self.plan = s, plan
        self.legs: List[Tuple[str, int, date, date]] = []
        d = s.req.start_date
        for city, n in plan:
            self.legs.append((city, n, d, d + timedelta(days=n)))
            d += timedelta(days=n)
        self.cities = [l[0] for l in self.legs]
        self.opts: List[List[dict]] = []
        self.fopts: List[List[dict]] = []
        self.links: List[dict] = []
        self.arr_flights: List[dict] = []
        self.ret_flights: List[dict] = []
        self.full_days: List[Tuple[date, str]] = []
        self.change_days: List[Tuple[date, str]] = []
        self.attr_min: Tuple[dict, int] = ({}, 0)      # (plan, cost); set in prepare()
        self.attr_rich: Tuple[dict, int] = ({}, 0)
        self._arr_cache: Dict[tuple, Optional[tuple]] = {}
        self._dep_cache: Dict[tuple, Optional[tuple]] = {}
        self.ok = False

    # ------------------------------------------------------------------ building
    def prepare(self) -> bool:
        s, req = self.s, self.s.req
        first, last = self.cities[0], self.cities[-1]
        self.arr_flights = [f for f in s.arr_flights if first in s.cat.airports[f["to"]].get("serves_cities", [])]
        self.ret_flights = [f for f in s.ret_flights if last in s.cat.airports[f["from"]].get("serves_cities", [])]
        if not self.arr_flights or not self.ret_flights:
            s.diag.fail("NO_CITY_PLAN_FOR_FLIGHTS",
                        f"Arrival flights land at {self._airports(s.arr_flights, 'to')} and return flights leave from "
                        f"{self._airports(s.ret_flights, 'from')}, but no city plan can start in a city served by one "
                        f"and end in a city served by the other.")
            return False
        # hotels
        for i, (city, n, check_in, _) in enumerate(self.legs):
            stats: dict = {}
            options = s.hotels(city, check_in, n, stats)
            if not options:
                why = "no room type fits your group" if stats.get("sold_out", 0) == 0 else "the fitting rooms are sold out on some nights"
                s.diag.fail("NO_ROOMS", f"No hotel in {city} can take {req.adults} adult(s) and {req.children} child(ren) "
                                         f"for {n} night(s) from {check_in:%d %b} ({why}).")
                return False
            edge = i == 0 or i == len(self.legs) - 1
            self.opts.append(options)
            self.fopts.append(pareto(options, by_area=edge))
        # city transfers
        for i in range(len(self.legs) - 1):
            link = s.link(self.cities[i], self.cities[i + 1], self.legs[i + 1][2])
            if link is None:
                s.diag.fail("NO_CITY_TRANSFER", f"No transfer from {self.cities[i]} to {self.cities[i + 1]} "
                                                f"runs on {self.legs[i + 1][2]:%d %b}.")
                return False
            self.links.append(link)
            self.change_days.append((self.legs[i + 1][2], self.cities[i + 1]))
        # attractions for full days
        change = {d for d, _ in self.change_days}
        for city, n, check_in, _check_out in self.legs:
            for j in range(n):
                d = check_in + timedelta(days=j)
                if d != req.start_date and d not in change:
                    self.full_days.append((d, city))
        for mode in ("MIN", "RICH"):
            plan_days = attr.plan_full_days(s.cat, self.full_days, req.adults, req.children, mode, req.interests)
            if plan_days is None:
                s.diag.fail("NOT_ENOUGH_ATTRACTIONS", "There are not enough open attractions to fill every full day "
                                                      "of this city plan.")
                return False
            cost = attr.plan_cost(plan_days, req.adults, req.children)
            if mode == "MIN":
                self.attr_min = (plan_days, cost)
            else:
                self.attr_rich = (plan_days, cost)
        self.link_cost = sum(l["price"] for l in self.links)
        self.link_minutes = sum(l["rec"]["duration_minutes"] for l in self.links)
        self.change_usable = sum(self._usable_from(l["arrive"], d) for l, (d, _) in zip(self.links, self.change_days, strict=False))
        self.ok = True
        return True

    @staticmethod
    def _airports(flights, key: str) -> str:
        return ", ".join(sorted({f[key] for f in flights})) or "none"

    @staticmethod
    def _usable_from(arrive, day: date) -> int:
        if arrive.date() != day:
            return 0
        lo = max(DAY_START_MIN, tod(arrive) + SETTLE_MIN)
        return max(0, DAY_END_MIN - lo)

    # ------------------------------------------------------------------ airport transfers
    def arr_transfer(self, flight: dict, opt: dict):
        key = (flight["flight_id"], opt["hotel"]["hotel_id"])
        if key not in self._arr_cache:
            self._arr_cache[key] = self._best_airport(flight["to"], self.cities[0], opt["hotel"]["area"],
                                                       lambda t: arrival_pickup(t, flight["_arr"]))
        return self._arr_cache[key]

    def dep_transfer(self, flight: dict, opt: dict):
        key = (flight["flight_id"], opt["hotel"]["hotel_id"])
        if key not in self._dep_cache:
            last_day = self.legs[-1][3]
            self._dep_cache[key] = self._best_airport(flight["from"], self.cities[-1], opt["hotel"]["area"],
                                                       lambda t: departure_pickup(t, flight["_dep"], last_day))
        return self._dep_cache[key]

    def _best_airport(self, airport: str, city: str, area: str, schedule):
        return best_airport_transfer(self.s.cat, self.s.req, airport, city, area, schedule)


# ============================================================================ session
class Session:
    def __init__(self, req: TripRequest, cat, inv: Inventory):
        self.req, self.cat, self.inv = req, cat, inv
        self.dep = cat.departure_airport(req.departure_city)
        self.code = cat.country_code(req.country)
        self.diag = Diag()
        self._hotels, self._links = {}, {}
        self.arr_flights: List[dict] = []
        self.ret_flights: List[dict] = []

    def hotels(self, city, check_in, nights, stats=None):
        key = (city, check_in, nights)
        if key not in self._hotels:
            st: dict = {}
            self._hotels[key] = (hotel_options(self.cat, self.inv, city, check_in, nights,
                                               self.req.adults, self.req.children, st), st)
        opts, st = self._hotels[key]
        if stats is not None:
            stats.update(st)
        return opts

    def link(self, a: str, b: str, day: date) -> Optional[dict]:
        key = (a, b, day)
        if key not in self._links:
            best = None
            for t in self.cat.link_transfers(self.req.country, a, b):
                times = intercity_departure(t, day)
                if times is None:
                    continue
                price = transfer_price(t, self.req.adults, self.req.children)
                k = (price, t["duration_minutes"], t["transfer_id"])
                if best is None or k < best[0]:
                    best = (k, {"rec": t, "pickup": times[0], "arrive": times[1], "price": price,
                                "quantity": transfer_quantity(t, self.req.adults, self.req.children),
                                "day": day, "from_city": a, "to_city": b})
            self._links[key] = best[1] if best else None
        return self._links[key]

    # ------------------------------------------------------------------ pre-checks
    def precheck(self) -> Optional[BuildResult]:
        r, cat = self.req, self.cat
        if r.start_date < WINDOW_FIRST or r.end_date > WINDOW_LAST:
            return BuildResult("NO_PACKAGE", reason_code="OUT_OF_WINDOW", message=(
                f"Our flights and rooms exist only from 1 to 20 April 2027. A {r.nights}-night trip starting "
                f"{r.start_date:%d %b %Y} would return on {r.end_date:%d %b %Y}; the first night must be on or after "
                f"1 Apr 2027 and the return flight on or before 20 Apr 2027."))
        arr_all = cat.arrivals(self.dep, self.code, r.start_date)
        if not arr_all:
            return self._none("NO_ARRIVAL_FLIGHT", f"No flights from {r.departure_city} to {r.country} land on "
                                                   f"{r.start_date:%d %b %Y}.")
        self.arr_flights = [f for f in arr_all if self.inv.seats_left(f) >= r.travelers]
        if not self.arr_flights:
            best = max(self.inv.seats_left(f) for f in arr_all)
            return self._none("INSUFFICIENT_SEATS_ARRIVAL",
                              f"{len(arr_all)} flight(s) from {r.departure_city} to {r.country} land on "
                              f"{r.start_date:%d %b %Y}, but none has {r.travelers} free seats (the best has {best}).")
        ret_all = cat.returns(self.dep, self.code, r.end_date)
        if not ret_all:
            return self._none("NO_RETURN_FLIGHT", f"No flights from {r.country} to {r.departure_city} leave on "
                                                  f"{r.end_date:%d %b %Y}.")
        self.ret_flights = [f for f in ret_all if self.inv.seats_left(f) >= r.travelers]
        if not self.ret_flights:
            best = max(self.inv.seats_left(f) for f in ret_all)
            return self._none("INSUFFICIENT_SEATS_RETURN",
                              f"{len(ret_all)} flight(s) from {r.country} to {r.departure_city} leave on "
                              f"{r.end_date:%d %b %Y}, but none has {r.travelers} free seats (the best has {best}).")
        return None

    @staticmethod
    def _none(code, msg):
        return BuildResult("NO_PACKAGE", reason_code=code, message=msg)
