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


# ---- direct (non-scanning) window search -------------------------------------------------
def _window_intervals(t: datetime, start: int, end: int):
    """Service-window intervals (as datetimes) for the service days around `t`."""
    end_eff = end if end >= start else end + 1440
    for back in (-1, 0, 1):
        day0 = datetime.combine(t.date() + timedelta(days=back), time.min)
        yield day0 + timedelta(minutes=start), day0 + timedelta(minutes=end_eff)


def earliest_in_window(not_before: datetime, start: int, end: int):
    """Earliest datetime >= not_before that is inside the service window, or None."""
    best = None
    for lo, hi in _window_intervals(not_before, start, end):
        if hi < not_before:
            continue
        cand = max(lo, not_before)
        if best is None or cand < best:
            best = cand
    return best


def latest_in_window(deadline: datetime, start: int, end: int):
    """Latest datetime <= deadline that is inside the service window, or None."""
    best = None
    for lo, hi in _window_intervals(deadline, start, end):
        if lo > deadline:
            continue
        cand = min(hi, deadline)
        if best is None or cand > best:
            best = cand
    return best
