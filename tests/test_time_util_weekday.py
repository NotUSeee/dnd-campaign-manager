"""next_date_matching_weekday — used to pre-fill the schedule modal."""
from datetime import datetime, timezone

import pytest

from plugin_module.core import time_util


def test_picks_next_week_when_today_matches():
    # Tuesday 2026-06-16 → schema dow 2
    base = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    result = time_util.next_date_matching_weekday(2, "UTC", after=base)
    # Should not return today; should return next Tuesday
    assert result == "2026-06-23"


def test_picks_next_matching_day_within_week():
    # Monday → next Tuesday is tomorrow
    base = datetime(2026, 6, 15, 12, 0, tzinfo=timezone.utc)  # Monday
    result = time_util.next_date_matching_weekday(2, "UTC", after=base)
    assert result == "2026-06-16"


def test_picks_next_sunday():
    # Tuesday → next Sunday (schema dow 0)
    base = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    result = time_util.next_date_matching_weekday(0, "UTC", after=base)
    assert result == "2026-06-21"


def test_returns_none_for_bad_input():
    base = datetime(2026, 6, 16, 12, 0, tzinfo=timezone.utc)
    assert time_util.next_date_matching_weekday(None, "UTC", after=base) is None
    assert time_util.next_date_matching_weekday(7, "UTC", after=base) is None
    assert time_util.next_date_matching_weekday(-1, "UTC", after=base) is None


def test_resolves_in_campaign_timezone():
    # Late-night UTC may be "next day" in NY
    base = datetime(2026, 6, 16, 4, 0, tzinfo=timezone.utc)  # Tuesday 04:00 UTC = Mon 00:00 EDT
    result = time_util.next_date_matching_weekday(1, "America/New_York", after=base)
    # In NY it's Monday, so next Monday is 2026-06-22 (a week away)
    assert result == "2026-06-22"
