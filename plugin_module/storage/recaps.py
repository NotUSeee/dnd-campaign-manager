"""Session recap storage: draft → posted lifecycle."""
from typing import Any, Dict, List, Optional


def create_draft(
    ctx,
    *,
    session_id: int,
    campaign_id: int,
    title: str,
    summary: str,
    highlights: str,
    loot: str,
    cliffhanger: str,
    author_user_id: str,
) -> Optional[Dict[str, Any]]:
    # INSERT/UPDATE then SELECT-back via the UNIQUE(session_id) index.
    ctx.sql.execute(
        """
        INSERT INTO dnd_recaps (
            session_id, campaign_id, discord_srv_id, title, summary,
            highlights, loot, cliffhanger, status, author_user_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s)
        ON CONFLICT (session_id) DO UPDATE
            SET title = EXCLUDED.title,
                summary = EXCLUDED.summary,
                highlights = EXCLUDED.highlights,
                loot = EXCLUDED.loot,
                cliffhanger = EXCLUDED.cliffhanger
        """,
        [
            int(session_id),
            int(campaign_id),
            int(ctx.server_id),
            str(title)[:200] if title else None,
            str(summary)[:4000],
            str(highlights)[:4000] if highlights else None,
            str(loot)[:2000] if loot else None,
            str(cliffhanger)[:1000] if cliffhanger else None,
            int(author_user_id),
        ],
    )
    return ctx.sql.query_one(
        """
        SELECT id, session_id, campaign_id, discord_srv_id, title, summary,
               highlights, loot, cliffhanger, dm_notes, status,
               posted_channel_id, posted_message_id, author_user_id,
               created_at, posted_at
          FROM dnd_recaps
         WHERE session_id = %s
        """,
        [int(session_id)],
    )


def get_recap(ctx, recap_id: int) -> Optional[Dict[str, Any]]:
    return ctx.sql.query_one(
        """
        SELECT id, session_id, campaign_id, discord_srv_id, title, summary,
               highlights, loot, cliffhanger, dm_notes, status,
               posted_channel_id, posted_message_id, author_user_id,
               created_at, posted_at
          FROM dnd_recaps
         WHERE id = %s AND discord_srv_id = %s
        """,
        [int(recap_id), int(ctx.server_id)],
    )


def get_recap_by_session(ctx, session_id: int) -> Optional[Dict[str, Any]]:
    return ctx.sql.query_one(
        """
        SELECT id, session_id, campaign_id, discord_srv_id, title, summary,
               highlights, loot, cliffhanger, dm_notes, status,
               posted_channel_id, posted_message_id, author_user_id,
               created_at, posted_at
          FROM dnd_recaps
         WHERE session_id = %s AND discord_srv_id = %s
        """,
        [int(session_id), int(ctx.server_id)],
    )


def list_posted_for_campaign(
    ctx, campaign_id: int, *, limit: int = 25
) -> List[Dict[str, Any]]:
    return ctx.sql.query(
        """
        SELECT r.id, r.session_id, r.title, r.summary, r.posted_at,
               r.posted_channel_id, r.posted_message_id, s.session_number
          FROM dnd_recaps r
          JOIN dnd_sessions s ON s.id = r.session_id
         WHERE r.campaign_id = %s AND r.discord_srv_id = %s AND r.status = 'posted'
         ORDER BY r.posted_at DESC
         LIMIT %s
        """,
        [int(campaign_id), int(ctx.server_id), int(limit)],
    )


def mark_posted(
    ctx, recap_id: int, *, channel_id: int, message_id: int
) -> int:
    return ctx.sql.execute(
        """
        UPDATE dnd_recaps
           SET status = 'posted',
               posted_channel_id = %s,
               posted_message_id = %s,
               posted_at = NOW()
         WHERE id = %s AND discord_srv_id = %s
        """,
        [int(channel_id), int(message_id), int(recap_id), int(ctx.server_id)],
    )


def set_dm_notes(ctx, recap_id: int, dm_notes: str) -> int:
    return ctx.sql.execute(
        """
        UPDATE dnd_recaps SET dm_notes = %s WHERE id = %s AND discord_srv_id = %s
        """,
        [str(dm_notes)[:4000] if dm_notes else None, int(recap_id), int(ctx.server_id)],
    )
