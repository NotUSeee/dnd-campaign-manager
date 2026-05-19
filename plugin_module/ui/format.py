"""Pure formatting helpers shared by embeds and handlers."""
from datetime import datetime, timezone
from typing import Any, Iterable, List

from plugin_module.core.time_util import (
    discord_timestamp,
    discord_timestamp_relative,
    parse_iso_dt,
)


def render_dt(dt: Any, *, style: str = "F") -> str:
    """Render a UTC datetime as a Discord auto-localized timestamp tag.

    Accepts datetime, ISO 8601 string, or None — the platform returns
    timestamps as ISO strings so any embed builder reading a row column
    directly will see a string.
    """
    dt = parse_iso_dt(dt) if not isinstance(dt, datetime) else dt
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return discord_timestamp(dt, style=style)


def render_dt_relative(dt: Any) -> str:
    dt = parse_iso_dt(dt) if not isinstance(dt, datetime) else dt
    if dt is None:
        return "—"
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return discord_timestamp_relative(dt)


def truncate(text: str, max_len: int = 1024, suffix: str = "…") -> str:
    if text is None:
        return ""
    s = str(text)
    if len(s) <= max_len:
        return s
    cut = max_len - len(suffix)
    if cut <= 0:
        return s[:max_len]
    return s[:cut] + suffix


def mention_user(user_id) -> str:
    if not user_id:
        return "Unknown"
    return f"<@{user_id}>"


def mention_channel(channel_id) -> str:
    if not channel_id:
        return "—"
    return f"<#{channel_id}>"


def mention_role(role_id) -> str:
    if not role_id:
        return "—"
    return f"<@&{role_id}>"


def join_user_mentions(user_ids: Iterable, *, limit: int = 15) -> str:
    ids = list(user_ids)
    if not ids:
        return "—"
    shown = [f"<@{u}>" for u in ids[:limit]]
    suffix = f" (+{len(ids) - limit} more)" if len(ids) > limit else ""
    return ", ".join(shown) + suffix


WEEKDAYS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def weekday_name(dow: int) -> str:
    if dow is None or not isinstance(dow, int):
        return "—"
    if 0 <= dow <= 6:
        return WEEKDAYS[dow]
    return "—"


def boolean_label(value, *, on: str = "Yes", off: str = "No") -> str:
    return on if bool(value) else off


def visibility_label(visibility: str) -> str:
    return {
        "public": "Public",
        "partial": "Partial",
        "dm_only": "DM-only",
    }.get(visibility, str(visibility))


def status_label(status: str) -> str:
    return {
        "active": "Active",
        "completed": "Completed",
        "failed": "Failed",
        "abandoned": "Abandoned",
        "scheduled": "Scheduled",
        "cancelled": "Cancelled",
        "draft": "Draft",
        "posted": "Posted",
        "archived": "Archived",
        "paused": "Paused",
    }.get(status, str(status).title())


def offsets_summary(offsets_minutes: List[int]) -> str:
    from plugin_module.core.time_util import format_offset_label
    if not offsets_minutes:
        return "none"
    return ", ".join(format_offset_label(int(o)) for o in offsets_minutes)
