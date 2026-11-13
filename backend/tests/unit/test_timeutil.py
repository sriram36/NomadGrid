from datetime import date, datetime

import pytest

from app.core.timeutil import hm, in_window_dt, weekday_code, fmt_dt, tod


def D(s):
    return datetime.fromisoformat(s)


def test_hm_parses_normal_midnight_and_24h():
    assert hm("06:00") == 360
    assert hm("00:30") == 30
    assert hm("24:00") == 1440


def test_weekday_code_for_menon_dates():
    assert weekday_code(date(2027, 4, 10)) == "SAT"
    assert weekday_code(date(2027, 4, 16)) == "FRI"


def test_tod_and_fmt():
    assert tod(D("2027-04-10T09:20")) == 560
    assert fmt_dt(D("2027-04-10T09:20:00")) == "2027-04-10T09:20"


# --- plain window 06:00-23:00, both ends inclusive
@pytest.mark.parametrize("t,expected", [
    ("2027-04-10T06:00", True),
    ("2027-04-10T23:00", True),
    ("2027-04-10T05:59", False),
    ("2027-04-10T23:01", False),
    ("2027-04-11T00:00", False),
])
def test_plain_window(t, expected):
    assert in_window_dt(D(t), hm("06:00"), hm("23:00")) is expected


# --- window ending 24:00: midnight at the end of the day counts
@pytest.mark.parametrize("t,expected", [
    ("2027-04-10T05:00", True),
    ("2027-04-10T23:59", True),
    ("2027-04-11T00:00", True),   # == 24:00 of 10 Apr
    ("2027-04-11T00:01", False),
    ("2027-04-10T04:59", False),
])
def test_window_ending_at_24h(t, expected):
    assert in_window_dt(D(t), hm("05:00"), hm("24:00")) is expected


# --- wrapping window 06:00-00:30 (runs past midnight)
@pytest.mark.parametrize("t,expected", [
    ("2027-04-10T06:00", True),
    ("2027-04-10T23:59", True),
    ("2027-04-11T00:00", True),
    ("2027-04-11T00:30", True),
    ("2027-04-11T00:31", False),
    ("2027-04-10T05:59", False),
    ("2027-04-10T03:00", False),
])
def test_wrapping_window(t, expected):
    assert in_window_dt(D(t), hm("06:00"), hm("00:30")) is expected


def test_all_day_window_always_true():
    for t in ["2027-04-10T00:00", "2027-04-10T12:00", "2027-04-10T23:59", "2027-04-11T00:00"]:
        assert in_window_dt(D(t), hm("00:00"), hm("24:00")) is True
