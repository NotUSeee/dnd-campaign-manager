"""RSVP storage: upsert per (session, user) + count aggregates."""
from typing import Any, Dict, List


VALID_STATUSES = ("attending", "maybe", "unavailable")


def upsert_rsvp(
    ctx, *, session_id: int, user_id: str, status: str, note: str = ""
) -> bool:
    if status not in VALID_STATUSES:
        return False
    ctx.sql.execute(
        """
        INSERT INTO dnd_session_rsvps (session_id, user_id, status, note, responded_at)
        VALUES (%s, %s, %s, %s, NOW())
        ON CONFLICT (session_id, user_id) DO UPDATE
            SET status = EXCLUDED.status,
                note = EXCLUDED.note,
                responded_at = NOW()
        """,
        [int(session_id), int(user_id), str(status), str(note)[:300] if note else None],
    )
    return True


def get_rsvp(ctx, *, session_id: int, user_id: str) -> Dict[str, Any]:
    return ctx.sql.query_one(
        "SELECT user_id, status, note, responded_at FROM dnd_session_rsvps "
        "WHERE session_id = %s AND user_id = %s",
        [int(session_id), int(user_id)],
    ) or {}


def list_rsvps_for_session(ctx, session_id: int) -> List[Dict[str, Any]]:
    return ctx.sql.query(
        "SELECT user_id, status, note, responded_at FROM dnd_session_rsvps "
        "WHERE session_id = %s ORDER BY responded_at",
        [int(session_id)],
    )


def counts_by_status(ctx, session_id: int) -> Dict[str, int]:
    rows = ctx.sql.query(
        "SELECT status, COUNT(*) AS cnt FROM dnd_session_rsvps "
        "WHERE session_id = %s GROUP BY status",
        [int(session_id)],
    )
    out = {s: 0 for s in VALID_STATUSES}
    for r in rows or []:
        out[str(r["status"])] = int(r["cnt"])
    return out


def list_user_ids_by_status(ctx, session_id: int, status: str) -> List[int]:
    rows = ctx.sql.query(
        "SELECT user_id FROM dnd_session_rsvps "
        "WHERE session_id = %s AND status = %s ORDER BY responded_at",
        [int(session_id), str(status)],
    )
    return [int(r["user_id"]) for r in rows or []]
