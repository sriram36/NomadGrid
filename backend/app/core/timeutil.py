"""Local-time helpers. All times are LOCAL to the place; no UTC conversion anywhere.

A clock time is minutes since midnight ("24:00" == 1440). A service window
`start..end` is inclusive on both ends; if end < start it wraps past midnight
(e.g. 06:00-00:30).
"""
from datetime import date, datetime, time, timedelta

_WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]


def hm(text: str) -> int:
    """'06:30' -> 390, '24:00' -> 1440."""
    h, m = text.split(":")
    return int(h) * 60 + int(m)


def tod(dt: datetime) -> int:
    """Minutes since midnight of a datetime."""
    return dt.hour * 60 + dt.minute


def at(day: date, minutes: int) -> datetime:
    """Datetime on `day` at `minutes` after midnight (may exceed 1440)."""
    return datetime.combine(day, time.min) + timedelta(minutes=minutes)


def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M")


def weekday_code(day: date) -> str:
    return _WEEKDAYS[day.weekday()]


def in_window_dt(t: datetime, start: int, end: int) -> bool:
    """Is datetime `t` inside the service window [start, end] (inclusive)?

    The window belongs to a service day D. It covers D+start .. D+end, and if the
    window wraps (end < start) it covers D+start .. D+1day+end. We test the
    service day of `t` itself and the day before it, which handles 24:00 and wraps.
    """
    end_eff = end if end >= start else end + 1440
    for back in (0, 1):
        day0 = datetime.combine(t.date() - timedelta(days=back), time.min)
        minutes = int((t - day0).total_seconds() // 60)
        if start <= minutes <= end_eff:
            return True
    return False
