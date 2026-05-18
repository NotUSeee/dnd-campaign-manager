"""advance_recurrence — weekly, biweekly, monthly_by_day, DST."""
from datetime import datetime, timezone

import pytest

from plugin_module.core import time_util


def test_weekly_adds_seven_days():
    start = datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc)  # Tuesday
    rule = {"freq": "WEEKLY", "interval": 1, "byweekday": "TU", "time_local": "19:00"}
    nxt = time_util.advance_recurrence(start, rule, tz_name="UTC")
    assert nxt is not None
    assert nxt.day == 23 and nxt.month == 6
    assert nxt.hour == 19


def test_biweekly_adds_fourteen_days():
    start = datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc)
    rule = {"freq": "BIWEEKLY", "interval": 2, "time_local": "19:00"}
    nxt = time_util.advance_recurrence(start, rule, tz_name="UTC")
    assert nxt is not None
    assert nxt.day == 30 and nxt.month == 6


def test_monthly_by_day_adds_one_month():
    start = datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc)
    rule = {"freq": "MONTHLY_BY_DAY", "interval": 1, "time_local": "19:00"}
    nxt = time_util.advance_recurrence(start, rule, tz_name="UTC")
    assert nxt is not None
    assert nxt.day == 15 and nxt.month == 7


def test_monthly_by_day_clamps_to_month_length():
    start = datetime(2026, 1, 31, 19, 0, tzinfo=timezone.utc)
    rule = {"freq": "MONTHLY_BY_DAY", "interval": 1, "time_local": "19:00"}
    nxt = time_util.advance_recurrence(start, rule, tz_name="UTC")
    assert nxt is not None
    # Feb has no 31st — should clamp to Feb 28
    assert nxt.month == 2 and nxt.day == 28


def test_returns_none_after_until_date():
    start = datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc)
    rule = {"freq": "WEEKLY", "interval": 1, "until": "2026-06-20", "time_local": "19:00"}
    nxt = time_util.advance_recurrence(start, rule, tz_name="UTC")
    assert nxt is None  # Next instance (June 23) is past the until date


def test_dst_preserves_local_wall_clock():
    """Schedule a recurring 7pm ET session straddling DST spring-forward (March 8 2026).

    Before DST: 7pm ET = 23:00 UTC (EST = UTC-5)
    After DST:  7pm ET = 23:00 UTC (EDT = UTC-4)
    Wait — that means UTC offset *changes* but local wall-clock stays the same.
    The recurrence should keep 7pm local, so UTC times will differ by 1h.
    """
    start = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)  # March 1 in NY = Feb 28 19:00 EST
    # Anchor at 19:00 NY local on March 1 (a Sunday)
    anchor_local = time_util.parse_date_time_local("2026-03-01", "19:00", "America/New_York")
    assert anchor_local is not None  # = 2026-03-02 00:00 UTC (still EST)

    rule = {"freq": "WEEKLY", "interval": 1, "time_local": "19:00"}
    nxt = time_util.advance_recurrence(anchor_local, rule, tz_name="America/New_York")
    assert nxt is not None
    # March 8 2026 in NY is the day DST starts (clocks jump to 03:00).
    # 19:00 NY on March 8 = EDT (UTC-4) = 23:00 UTC.
    assert nxt.hour == 23  # Was 00:00 UTC before DST, now 23:00 the previous day in UTC
