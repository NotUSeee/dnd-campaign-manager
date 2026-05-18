"""Timezone, date parsing, and recurrence advancement.

All persisted timestamps are UTC (Postgres TIMESTAMPTZ).
User-facing display uses Discord's native ``<t:UNIX:F>`` formatter which
renders in the viewer's local timezone — no server-side formatting needed
for most cases.
"""
from __future__ import annotations

import re
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, Optional

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
except ImportError:  # pragma: no cover — Python < 3.9 not supported
    ZoneInfo = None  # type: ignore[assignment]
    ZoneInfoNotFoundError = Exception  # type: ignore[misc,assignment]


_DATE_RE = re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$")
_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


WEEKDAY_TO_CRON = {"SU": 0, "MO": 1, "TU": 2, "WE": 3, "TH": 4, "FR": 5, "SA": 6}


def validate_timezone(tz_name: str) -> bool:
    if not tz_name:
        return False
    if ZoneInfo is None:
        return tz_name.upper() == "UTC"
    try:
        ZoneInfo(tz_name)
        return True
    except ZoneInfoNotFoundError:
        return False
    except Exception:
        return False


def _tz(name: str):
    if ZoneInfo is None or not name or name.upper() == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(name)
    except Exception:
        return timezone.utc


def parse_date_time_local(date_str: str, time_str: str, tz_name: str) -> Optional[datetime]:
    """Parse 'YYYY-MM-DD' + 'HH:MM' as a local time in tz_name, return aware UTC datetime."""
    if not date_str or not time_str:
        return None
    d_match = _DATE_RE.match(date_str.strip())
    t_match = _TIME_RE.match(time_str.strip())
    if not d_match or not t_match:
        return None
    try:
        year, month, day = int(d_match.group(1)), int(d_match.group(2)), int(d_match.group(3))
        hour, minute = int(t_match.group(1)), int(t_match.group(2))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            return None
        local = datetime(year, month, day, hour, minute, 0, tzinfo=_tz(tz_name))
        return local.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        return None


def to_unix(dt: datetime) -> int:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def discord_timestamp(dt: datetime, style: str = "F") -> str:
    """Render a datetime as Discord's auto-localized timestamp marker."""
    return f"<t:{to_unix(dt)}:{style}>"


def discord_timestamp_relative(dt: datetime) -> str:
    return discord_timestamp(dt, "R")


# ── Recurrence advancement ────────────────────────────────────────────────


def advance_recurrence(
    current_utc: datetime, rule: Dict[str, Any], tz_name: str = "UTC"
) -> Optional[datetime]:
    """Given a session's start (UTC) and recurrence rule, return the next start.

    Supported rule shapes:
      {"freq": "WEEKLY",  "interval": 1, "byweekday": "TU"|null, "time_local": "HH:MM"|null, "until": "YYYY-MM-DD"|null}
      {"freq": "BIWEEKLY", ...}   (equivalent to WEEKLY with interval=2)
      {"freq": "MONTHLY_BY_DAY", ...}  (same day-of-month; falls back to last day)

    The next instance preserves the same wall-clock time-of-day in tz_name so
    that DST transitions don't drift the session by an hour.

    Returns the next datetime (UTC, tz-aware), or None if past `until`.
    """
    if not rule or not isinstance(rule, dict):
        return None

    freq = str(rule.get("freq") or "").upper()
    interval = max(1, int(rule.get("interval") or 1))

    if current_utc.tzinfo is None:
        current_utc = current_utc.replace(tzinfo=timezone.utc)
    local = current_utc.astimezone(_tz(tz_name))

    if freq == "BIWEEKLY":
        freq = "WEEKLY"
        interval = max(interval, 2)

    if freq == "WEEKLY":
        days = 7 * interval
        next_local = local + timedelta(days=days)
    elif freq == "MONTHLY_BY_DAY":
        next_local = _add_months_same_day(local, interval)
    else:
        return None

    # Re-anchor to time_local if provided (handles cases where the rule overrides)
    time_local = rule.get("time_local")
    if time_local and isinstance(time_local, str):
        t_match = _TIME_RE.match(time_local.strip())
        if t_match:
            hour, minute = int(t_match.group(1)), int(t_match.group(2))
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                next_local = next_local.replace(
                    hour=hour, minute=minute, second=0, microsecond=0
                )

    next_utc = next_local.astimezone(timezone.utc)

    until = rule.get("until")
    if until and isinstance(until, str):
        d_match = _DATE_RE.match(until.strip())
        if d_match:
            try:
                until_dt = datetime(
                    int(d_match.group(1)),
                    int(d_match.group(2)),
                    int(d_match.group(3)),
                    23,
                    59,
                    59,
                    tzinfo=_tz(tz_name),
                ).astimezone(timezone.utc)
                if next_utc > until_dt:
                    return None
            except (ValueError, OverflowError):
                pass

    return next_utc


def _add_months_same_day(dt: datetime, months: int) -> datetime:
    """Add `months` months, clamping day to the new month's length."""
    new_month = dt.month + months
    new_year = dt.year + (new_month - 1) // 12
    new_month = ((new_month - 1) % 12) + 1
    # Walk back from the original day until the date is valid
    for trial_day in range(dt.day, 0, -1):
        try:
            return dt.replace(year=new_year, month=new_month, day=trial_day)
        except ValueError:
            continue
    return dt  # unreachable; placates linters


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def next_date_matching_weekday(
    dow: int, tz_name: str = "UTC", *, after: Optional[datetime] = None
) -> Optional[str]:
    """Return YYYY-MM-DD of the next date whose weekday matches `dow`.

    `dow` uses the same convention as the schema (0=Sunday … 6=Saturday).
    Resolves the date in the campaign timezone so "next Tuesday" reflects
    what the DM means in their local week. Returns None on bad input.
    """
    if dow is None or not isinstance(dow, int) or not (0 <= dow <= 6):
        return None
    base = after or now_utc()
    local = base.astimezone(_tz(tz_name))
    # Python weekday(): Monday=0 … Sunday=6. Schema uses Sunday=0 … Saturday=6.
    # Map schema dow → python weekday: schema 0 (Sun) → python 6, schema 1 → 0, etc.
    target_py = (dow - 1) % 7
    cur_py = local.weekday()
    days_ahead = (target_py - cur_py) % 7
    if days_ahead == 0:
        days_ahead = 7  # if today matches, pick next week (don't default to "today")
    target = local + timedelta(days=days_ahead)
    return f"{target.year:04d}-{target.month:02d}-{target.day:02d}"


def compute_next_reminder_due_at(
    starts_at: datetime, offsets_minutes: list, already_sent: list
) -> Optional[datetime]:
    """Pick the earliest scheduled reminder time that hasn't been sent yet."""
    if not starts_at:
        return None
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    sent = set(int(x) for x in (already_sent or []))
    pending = [int(o) for o in (offsets_minutes or []) if int(o) not in sent and int(o) > 0]
    if not pending:
        return None
    # The reminder for a 24h offset fires at `starts_at - 24h`. We want the
    # earliest unsent reminder's fire time, even if it's in the past (the
    # dispatcher's staleness guard handles old fire times).
    return min(starts_at - timedelta(minutes=o) for o in pending)


def is_reminder_offset_relevant(
    offset_minutes: int, starts_at: datetime, now: datetime, max_stale_minutes: int = 30
) -> bool:
    """True if this offset is still worth firing right now.

    Skips an offset if:
    - the session is already more than `max_stale_minutes` past
    - the offset's intended fire time hasn't arrived yet (too early)
    - we've burned through more than half the intended lead time, and the
      offset is large enough that the label would be misleading
      (e.g. a "24h reminder" fired 15 min before the session)
    """
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    minutes_until = int((starts_at - now).total_seconds() // 60)
    if minutes_until < -max_stale_minutes:
        return False
    if minutes_until > offset_minutes + 5:
        return False
    # Stale label guard: a 1440-min reminder fired 30 min before the session is
    # misleading ("24h" but actually 30m). Only fire if we're still within the
    # back-half of the intended lead time. Tiny offsets (< 30m) skip this check.
    if offset_minutes >= 30 and minutes_until < offset_minutes - max(offset_minutes // 2, max_stale_minutes):
        return False
    return True


def format_offset_label(minutes: int) -> str:
    """Human-friendly label for a reminder offset: 24h, 2h, 15m, etc."""
    if minutes >= 1440 and minutes % 1440 == 0:
        return f"{minutes // 1440}d"
    if minutes >= 60 and minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m"


def format_duration(minutes: int) -> str:
    if minutes <= 0:
        return "0m"
    h, m = divmod(int(minutes), 60)
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m"
