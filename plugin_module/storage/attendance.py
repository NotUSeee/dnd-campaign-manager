"""Post-session attendance: did the player actually show up?"""
from typing import Any, Dict, List


def log_attendance(
    ctx, *, session_id: int, user_id: str, attended: bool, note: str = ""
) -> int:
    return ctx.sql.execute(
        """
        INSERT INTO dnd_session_attendance (session_id, user_id, attended, note)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (session_id, user_id) DO UPDATE
            SET attended = EXCLUDED.attended,
                note = EXCLUDED.note,
                logged_at = NOW()
        """,
        [int(session_id), int(user_id), bool(attended), str(note)[:300] if note else None],
    )


def list_attendance_for_session(ctx, session_id: int) -> List[Dict[str, Any]]:
    return ctx.sql.query(
        "SELECT user_id, attended, note, logged_at FROM dnd_session_attendance "
        "WHERE session_id = %s ORDER BY logged_at",
        [int(session_id)],
    )


def attendance_by_user_for_campaign(
    ctx, campaign_id: int, user_id: str
) -> Dict[str, int]:
    """Return {attended: int, missed: int} totals across all sessions in the campaign."""
    row = ctx.sql.query_one(
        """
        SELECT
            COUNT(*) FILTER (WHERE a.attended) AS attended,
            COUNT(*) FILTER (WHERE NOT a.attended) AS missed
          FROM dnd_session_attendance a
          JOIN dnd_sessions s ON s.id = a.session_id
         WHERE s.campaign_id = %s AND a.user_id = %s
        """,
        [int(campaign_id), int(user_id)],
    )
    if not row:
        return {"attended": 0, "missed": 0}
    return {
        "attended": int(row.get("attended") or 0),
        "missed": int(row.get("missed") or 0),
    }
