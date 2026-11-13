"""The direct window search must give exactly what a minute-by-minute scan gives (it replaced the scan for speed)."""
import random
from datetime import datetime, timedelta

from app.core.timeutil import earliest_in_window, in_window_dt, latest_in_window


def scan_earliest(t, s, e, horizon=3 * 1440):
    for i in range(horizon):
        c = t + timedelta(minutes=i)
        if in_window_dt(c, s, e):
            return c
    return None


def scan_latest(t, s, e, horizon=3 * 1440):
    for i in range(horizon):
        c = t - timedelta(minutes=i)
        if in_window_dt(c, s, e):
            return c
    return None


def test_direct_search_matches_the_scan_on_random_windows():
    rnd = random.Random(5)
    base = datetime(2027, 4, 10)
    for _ in range(400):
        s = rnd.choice([0, 300, 330, 360, 390, 480, rnd.randint(0, 1439)])
        e = rnd.choice([1440, 1380, 1320, 30, 60, rnd.randint(0, 1440)])
        t = base + timedelta(minutes=rnd.randint(0, 2 * 1440))
        assert earliest_in_window(t, s, e) == scan_earliest(t, s, e), (s, e, t)
        assert latest_in_window(t, s, e) == scan_latest(t, s, e), (s, e, t)


def test_known_edges():
    t = datetime(2027, 4, 10, 23, 30)
    assert earliest_in_window(t, 360, 30) == t                                     # inside a wrapping window
    assert earliest_in_window(datetime(2027, 4, 11, 0, 31), 360, 30) == datetime(2027, 4, 11, 6, 0)
    assert latest_in_window(datetime(2027, 4, 11, 3, 0), 360, 30) == datetime(2027, 4, 11, 0, 30)
    assert earliest_in_window(datetime(2027, 4, 10, 23, 0), 0, 1440) == datetime(2027, 4, 10, 23, 0)
