"""parse_date_time_local, compute_next_reminder_due_at, is_reminder_offset_relevant."""
from datetime import datetime, timedelta, timezone

import pytest

from plugin_module.core import time_util


def test_validate_timezone_accepts_iana():
    assert time_util.validate_timezone("UTC") is True
    assert time_util.validate_timezone("America/New_York") is True


def test_validate_timezone_rejects_garbage():
    assert time_util.validate_timezone("Not/A/Zone") is False
    assert time_util.validate_timezone("") is False


def test_parse_date_time_local_utc():
    dt = time_util.parse_date_time_local("2026-06-15", "19:00", "UTC")
    assert dt is not None
    assert dt.year == 2026 and dt.month == 6 and dt.day == 15
    assert dt.hour == 19 and dt.minute == 0
    assert dt.tzinfo == timezone.utc


def test_parse_date_time_local_with_timezone():
    dt = time_util.parse_date_time_local("2026-06-15", "19:00", "America/New_York")
    assert dt is not None
    # NY in June is EDT (UTC-4) → 19:00 local = 23:00 UTC
    assert dt.hour == 23 and dt.tzinfo == timezone.utc


def test_parse_date_time_local_rejects_bad_input():
    assert time_util.parse_date_time_local("not-a-date", "19:00", "UTC") is None
    assert time_util.parse_date_time_local("2026-06-15", "25:00", "UTC") is None
    assert time_util.parse_date_time_local("", "", "UTC") is None


def test_compute_next_reminder_due_at_basic():
    starts = datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc)
    due = time_util.compute_next_reminder_due_at(starts, [1440, 120, 15], [])
    # earliest unsent fire = 24h before starts
    assert due == starts - timedelta(minutes=1440)


def test_compute_next_reminder_due_at_skips_sent():
    starts = datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc)
    # 24h offset already sent — next is 2h
    due = time_util.compute_next_reminder_due_at(starts, [1440, 120, 15], [1440])
    assert due == starts - timedelta(minutes=120)


def test_compute_next_reminder_due_at_returns_none_when_all_sent():
    starts = datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc)
    assert time_util.compute_next_reminder_due_at(starts, [1440, 120, 15], [1440, 120, 15]) is None


def test_is_reminder_offset_relevant_normal_window():
    starts = datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc)
    now = starts - timedelta(minutes=15)  # 15m before
    assert time_util.is_reminder_offset_relevant(15, starts, now) is True


def test_is_reminder_offset_relevant_skips_stale_post_session():
    starts = datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc)
    now = starts + timedelta(hours=2)  # session was 2h ago
    # Should skip — way past
    assert time_util.is_reminder_offset_relevant(15, starts, now) is False


def test_is_reminder_offset_relevant_skips_overdue_24h_reminder_for_imminent_session():
    starts = datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc)
    now = starts - timedelta(minutes=30)  # 30m before
    # 24h offset's window is 23h ahead of now — way past, skip
    assert time_util.is_reminder_offset_relevant(1440, starts, now) is False


def test_format_offset_label():
    assert time_util.format_offset_label(15) == "15m"
    assert time_util.format_offset_label(60) == "1h"
    assert time_util.format_offset_label(120) == "2h"
    assert time_util.format_offset_label(1440) == "1d"
    assert time_util.format_offset_label(2880) == "2d"
    # non-round values fall back to minutes
    assert time_util.format_offset_label(45) == "45m"


def test_format_duration():
    assert time_util.format_duration(0) == "0m"
    assert time_util.format_duration(60) == "1h"
    assert time_util.format_duration(90) == "1h 30m"
    assert time_util.format_duration(240) == "4h"
    assert time_util.format_duration(30) == "30m"


def test_discord_timestamp_includes_unix():
    dt = datetime(2026, 6, 15, 19, 0, tzinfo=timezone.utc)
    assert time_util.discord_timestamp(dt, "F") == f"<t:{int(dt.timestamp())}:F>"
    assert "<t:" in time_util.discord_timestamp_relative(dt)
