"""Sessions CRUD + recurrence series management."""
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def create_session(
    ctx,
    *,
    campaign_id: int,
    title: str,
    notes_for_players: str,
    starts_at: datetime,
    duration_minutes: int,
    created_by_user_id: str,
    announce_channel_id: Optional[int] = None,
    series_id: Optional[int] = None,
    recurrence_rule: Optional[Dict[str, Any]] = None,
    next_reminder_due_at: Optional[datetime] = None,
) -> Optional[Dict[str, Any]]:
    """Insert a session row. Returns the row dict."""
    # Compute next session_number for the campaign
    next_num = ctx.sql.scalar(
        """
        SELECT COALESCE(MAX(session_number), 0) + 1
          FROM dnd_sessions
         WHERE campaign_id = %s
        """,
        [int(campaign_id)],
    )
    # INSERT then SELECT-back (platform's sql.query rejects INSERT…RETURNING).
    # Identify the just-inserted row by (campaign_id, starts_at, created_by_user_id)
    # — same DM can't double-book the exact same start moment in the same campaign.
    affected = ctx.sql.execute(
        """
        INSERT INTO dnd_sessions (
            campaign_id, discord_srv_id, session_number, title,
            notes_for_players, starts_at, duration_minutes,
            announce_channel_id, series_id, recurrence_rule,
            next_reminder_due_at, created_by_user_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            int(campaign_id),
            int(ctx.server_id),
            int(next_num or 1),
            str(title)[:200] if title else None,
            str(notes_for_players)[:2000] if notes_for_players else None,
            starts_at,
            int(duration_minutes),
            int(announce_channel_id) if announce_channel_id else None,
            int(series_id) if series_id else None,
            json.dumps(recurrence_rule) if recurrence_rule else None,
            next_reminder_due_at,
            int(created_by_user_id),
        ],
    )
    if not affected:
        return None
    row = ctx.sql.query_one(
        """
        SELECT id, campaign_id, discord_srv_id, session_number, title,
               notes_for_players, starts_at, duration_minutes, status,
               announce_channel_id, announce_message_id, series_id,
               recurrence_rule, next_reminder_due_at, reminder_offsets_sent,
               created_by_user_id, created_at, updated_at
          FROM dnd_sessions
         WHERE campaign_id = %s AND starts_at = %s AND created_by_user_id = %s
         ORDER BY id DESC
         LIMIT 1
        """,
        [int(campaign_id), starts_at, int(created_by_user_id)],
    )
    return _coerce_session(row)


def get_session(ctx, session_id: int) -> Optional[Dict[str, Any]]:
    row = ctx.sql.query_one(
        """
        SELECT id, campaign_id, discord_srv_id, session_number, title,
               notes_for_players, starts_at, duration_minutes, status,
               announce_channel_id, announce_message_id, series_id,
               recurrence_rule, next_reminder_due_at, reminder_offsets_sent,
               created_by_user_id, created_at, updated_at
          FROM dnd_sessions
         WHERE id = %s AND discord_srv_id = %s
        """,
        [int(session_id), int(ctx.server_id)],
    )
    return _coerce_session(row)


def list_sessions_for_campaign(
    ctx, campaign_id: int, *, scope: str = "upcoming", limit: int = 25
) -> List[Dict[str, Any]]:
    if scope == "past":
        sql = """
            SELECT id, session_number, title, starts_at, duration_minutes,
                   status, announce_channel_id, announce_message_id
              FROM dnd_sessions
             WHERE campaign_id = %s AND discord_srv_id = %s
               AND (status = 'completed' OR (status = 'scheduled' AND starts_at < NOW()))
             ORDER BY starts_at DESC
             LIMIT %s
        """
    elif scope == "all":
        sql = """
            SELECT id, session_number, title, starts_at, duration_minutes,
                   status, announce_channel_id, announce_message_id
              FROM dnd_sessions
             WHERE campaign_id = %s AND discord_srv_id = %s
             ORDER BY starts_at DESC
             LIMIT %s
        """
    else:  # upcoming
        sql = """
            SELECT id, session_number, title, starts_at, duration_minutes,
                   status, announce_channel_id, announce_message_id
              FROM dnd_sessions
             WHERE campaign_id = %s AND discord_srv_id = %s
               AND status = 'scheduled' AND starts_at >= NOW()
             ORDER BY starts_at
             LIMIT %s
        """
    rows = ctx.sql.query(sql, [int(campaign_id), int(ctx.server_id), int(limit)])
    return [_coerce_session(r) for r in rows]


def next_session_for_campaign(ctx, campaign_id: int) -> Optional[Dict[str, Any]]:
    row = ctx.sql.query_one(
        """
        SELECT id, session_number, title, starts_at, duration_minutes, status,
               announce_channel_id, announce_message_id
          FROM dnd_sessions
         WHERE campaign_id = %s AND discord_srv_id = %s
           AND status = 'scheduled' AND starts_at >= NOW()
         ORDER BY starts_at
         LIMIT 1
        """,
        [int(campaign_id), int(ctx.server_id)],
    )
    return _coerce_session(row)


def update_announce_message(
    ctx, session_id: int, *, channel_id: int, message_id: int
) -> int:
    return ctx.sql.execute(
        """
        UPDATE dnd_sessions
           SET announce_channel_id = %s, announce_message_id = %s, updated_at = NOW()
         WHERE id = %s AND discord_srv_id = %s
        """,
        [int(channel_id), int(message_id), int(session_id), int(ctx.server_id)],
    )


def cancel_session(ctx, session_id: int) -> int:
    return ctx.sql.execute(
        """
        UPDATE dnd_sessions
           SET status = 'cancelled', next_reminder_due_at = NULL, updated_at = NOW()
         WHERE id = %s AND discord_srv_id = %s AND status = 'scheduled'
        """,
        [int(session_id), int(ctx.server_id)],
    )


def mark_completed(ctx, session_id: int) -> int:
    return ctx.sql.execute(
        """
        UPDATE dnd_sessions SET status = 'completed', next_reminder_due_at = NULL,
               updated_at = NOW()
         WHERE id = %s AND discord_srv_id = %s AND status = 'scheduled'
        """,
        [int(session_id), int(ctx.server_id)],
    )


def set_recurrence_rule(ctx, session_id: int, rule: Optional[Dict[str, Any]]) -> int:
    return ctx.sql.execute(
        """
        UPDATE dnd_sessions
           SET recurrence_rule = %s, updated_at = NOW()
         WHERE id = %s AND discord_srv_id = %s
        """,
        [json.dumps(rule) if rule else None, int(session_id), int(ctx.server_id)],
    )


def series_anchor(ctx, session_id: int) -> Optional[Dict[str, Any]]:
    """Return the anchor session (with recurrence_rule). May be the session itself."""
    s = get_session(ctx, session_id)
    if not s:
        return None
    if s.get("recurrence_rule"):
        return s
    series_id = s.get("series_id")
    if series_id:
        return get_session(ctx, int(series_id))
    return None


def series_session_count_future(ctx, series_id: int) -> int:
    val = ctx.sql.scalar(
        """
        SELECT COUNT(*) FROM dnd_sessions
         WHERE (series_id = %s OR id = %s)
           AND status = 'scheduled' AND starts_at > NOW()
        """,
        [int(series_id), int(series_id)],
    )
    return int(val or 0)


def series_needing_extension(ctx, *, threshold: int) -> List[int]:
    """Return series_ids where future scheduled sessions <= threshold."""
    rows = ctx.sql.query(
        """
        SELECT s.id AS series_id
          FROM dnd_sessions s
         WHERE s.recurrence_rule IS NOT NULL
           AND (SELECT COUNT(*) FROM dnd_sessions f
                 WHERE (f.series_id = s.id OR f.id = s.id)
                   AND f.status = 'scheduled'
                   AND f.starts_at > NOW()) <= %s
        """,
        [int(threshold)],
    )
    return [int(r["series_id"]) for r in rows]


def latest_in_series(ctx, series_id: int) -> Optional[Dict[str, Any]]:
    """Latest (future) session in the series, used as the anchor for advancing."""
    row = ctx.sql.query_one(
        """
        SELECT id, campaign_id, discord_srv_id, title, notes_for_players,
               starts_at, duration_minutes, announce_channel_id, series_id,
               recurrence_rule, created_by_user_id
          FROM dnd_sessions
         WHERE (series_id = %s OR id = %s) AND status = 'scheduled'
         ORDER BY starts_at DESC
         LIMIT 1
        """,
        [int(series_id), int(series_id)],
    )
    return _coerce_session(row)


def find_due_reminders(ctx, now_utc: datetime, *, limit: int = 50) -> List[Dict[str, Any]]:
    rows = ctx.sql.query(
        """
        SELECT id, campaign_id, discord_srv_id, session_number, title,
               starts_at, duration_minutes, announce_channel_id,
               announce_message_id, reminder_offsets_sent
          FROM dnd_sessions
         WHERE status = 'scheduled'
           AND next_reminder_due_at IS NOT NULL
           AND next_reminder_due_at <= %s
         ORDER BY next_reminder_due_at
         LIMIT %s
        """,
        [now_utc, int(limit)],
    )
    return [_coerce_session(r) for r in rows]


def mark_offset_sent_atomic(ctx, session_id: int, offset_minutes: int) -> bool:
    """Atomic at-most-once: succeed iff offset wasn't already in the array."""
    rows = ctx.sql.execute(
        """
        UPDATE dnd_sessions
           SET reminder_offsets_sent = array_append(reminder_offsets_sent, %s),
               updated_at = NOW()
         WHERE id = %s
           AND NOT (%s = ANY(reminder_offsets_sent))
        """,
        [int(offset_minutes), int(session_id), int(offset_minutes)],
    )
    return int(rows or 0) > 0


def set_next_reminder_due_at(ctx, session_id: int, next_due: Optional[datetime]) -> int:
    return ctx.sql.execute(
        """
        UPDATE dnd_sessions
           SET next_reminder_due_at = %s, updated_at = NOW()
         WHERE id = %s
        """,
        [next_due, int(session_id)],
    )


def _coerce_session(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Coerce JSON-safe row values back into Python types.

    Platform SQL surface returns ``TIMESTAMPTZ`` as ISO strings and JSONB
    as parsed structures (sometimes as strings if not auto-decoded). We
    materialize the ``recurrence_rule`` dict and convert the timestamp
    columns we do arithmetic on into UTC-aware ``datetime`` objects.
    """
    if not row:
        return None
    rule = row.get("recurrence_rule")
    if isinstance(rule, str):
        try:
            row["recurrence_rule"] = json.loads(rule)
        except (ValueError, TypeError):
            row["recurrence_rule"] = None
    from plugin_module.core.time_util import parse_iso_dt
    for col in ("starts_at", "next_reminder_due_at", "created_at", "updated_at"):
        if col in row:
            row[col] = parse_iso_dt(row[col])
    return row
