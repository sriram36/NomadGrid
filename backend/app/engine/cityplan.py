"""City plans: ordered distinct cities, each >= 2 nights, nights summing to the trip length."""
from itertools import permutations
from typing import Iterator, List, Optional, Tuple

Plan = Tuple[Tuple[str, int], ...]   # ((city, nights), ...)

MIN_NIGHTS_PER_CITY = 2


def compositions(total: int, parts: int, minimum: int) -> Iterator[Tuple[int, ...]]:
    """All ways to split `total` into `parts` integers, each >= minimum."""
    if parts == 1:
        if total >= minimum:
            yield (total,)
        return
    for first in range(minimum, total - minimum * (parts - 1) + 1):
        for rest in compositions(total - first, parts - 1, minimum):
            yield (first,) + rest


def generate_plans(cat, country: str, nights: int, max_cities: Optional[int] = None) -> List[Plan]:
    cities = cat.cities_of(country)
    links = cat.links_of(country)
    plans: List[Plan] = []
    limit = min(len(cities), nights // MIN_NIGHTS_PER_CITY)
    if max_cities is not None:
        limit = min(limit, max_cities)
    for k in range(1, limit + 1):
        for perm in permutations(cities, k):
            if not all((a, b) in links for a, b in zip(perm, perm[1:])):
                continue
            for comp in compositions(nights, k, MIN_NIGHTS_PER_CITY):
                plans.append(tuple(zip(perm, comp)))
    return plans


def preferred_city_count(nights: int, n_cities: int) -> int:
    """k* = clamp(floor(N/3), 1, #cities): about one city per 3 nights."""
    return max(1, min(nights // 3, n_cities, nights // MIN_NIGHTS_PER_CITY))
