"""Reminder dispatcher helpers.

Most of the queries live in sessions.py — this module holds the small bits
that are about *dispatching* (looking up campaign settings during a tick,
computing the next due time, etc.).
"""
from datetime import datetime
from typing import Any, Dict, List, Optional


def get_settings_for_session(ctx, session_id: int) -> Optional[Dict[str, Any]]:
    """Fetch the settings row joined via the session's campaign."""
    return ctx.sql.query_one(
        """
        SELECT cs.campaign_id, cs.reminder_offsets_minutes,
               cs.reminder_channel_id, cs.announce_channel_id,
               cs.player_role_id, cs.ping_on_reminders,
               cs.rsvp_required,
               c.name AS campaign_name, c.timezone
          FROM dnd_sessions s
          JOIN dnd_campaign_settings cs ON cs.campaign_id = s.campaign_id
          JOIN dnd_campaigns c ON c.id = s.campaign_id
         WHERE s.id = %s
        """,
        [int(session_id)],
    )


def party_user_ids_without_rsvp(ctx, session_id: int, campaign_id: int) -> List[int]:
    """Active party members who haven't responded to this session yet."""
    rows = ctx.sql.query(
        """
        SELECT p.user_id
          FROM dnd_party_members p
         WHERE p.campaign_id = %s AND p.is_active = TRUE
           AND NOT EXISTS (
                 SELECT 1 FROM dnd_session_rsvps r
                  WHERE r.session_id = %s AND r.user_id = p.user_id
               )
         ORDER BY p.joined_at
         LIMIT 50
        """,
        [int(campaign_id), int(session_id)],
    )
    return [int(r["user_id"]) for r in rows]
