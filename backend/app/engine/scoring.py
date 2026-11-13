"""The quality score: stay 40, flights 20, experience 15, time 15, budget fit 10."""

from app.config import DAY_END_MIN, DAY_START_MIN
from app.core.timeutil import tod

FULL_DAY_MINUTES = DAY_END_MIN - DAY_START_MIN        # 780


def flight_points(a: dict, r: dict) -> float:
    pts = (5 if a["stops"] == 0 else 0) + (5 if r["stops"] == 0 else 0)
    pts += 5 if 360 <= tod(a["_arr"]) <= 1200 else 0
    pts += 5 if 480 <= tod(r["_dep"]) <= 1200 else 0
    return float(pts)


def experience_points(plan, full_days: int, children: int) -> float:
    atts = [a for v in plan.values() for a, _, _ in v]
    cov = min(1.0, len(atts) / (2 * full_days)) if full_days else 1.0
    variety = min(len({a["category"] for a in atts}), 4) / 4 if atts else 0.0
    if children == 0 or not atts:
        suit = 1.0
    else:
        suit = sum(1 for a in atts if a.get("child_friendly")) / len(atts)
    return 9 * cov + 3 * variety + 3 * suit


def time_points(transit: int, usable: int, n_days: int, tmin: int, tmax: int) -> float:
    t = 9.0 if tmax <= tmin else 9.0 * (1 - (transit - tmin) / (tmax - tmin))
    return max(0.0, min(9.0, t)) + 6.0 * min(1.0, usable / (FULL_DAY_MINUTES * n_days))


def fit_points(total: int, budget: int) -> float:
    return 10.0 * max(0.0, min(1.0, (total / budget - 0.5) / 0.4))
