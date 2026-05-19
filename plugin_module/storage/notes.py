"""DM-only notes. Permission gating happens in the handler; this module is mechanical."""
from typing import Any, Dict, List, Optional


def create_note(
    ctx,
    *,
    campaign_id: int,
    title: str,
    body: str,
    author_user_id: str,
) -> Optional[Dict[str, Any]]:
    affected = ctx.sql.execute(
        """
        INSERT INTO dnd_dm_notes (campaign_id, discord_srv_id, title, body, author_user_id)
        VALUES (%s, %s, %s, %s, %s)
        """,
        [
            int(campaign_id),
            int(ctx.server_id),
            str(title)[:200],
            str(body)[:4000],
            int(author_user_id),
        ],
    )
    if not affected:
        return None
    return ctx.sql.query_one(
        """
        SELECT id, campaign_id, discord_srv_id, title, body, author_user_id,
               created_at, updated_at
          FROM dnd_dm_notes
         WHERE campaign_id = %s AND author_user_id = %s AND title = %s
         ORDER BY id DESC LIMIT 1
        """,
        [int(campaign_id), int(author_user_id), str(title)[:200]],
    )


def get_note(ctx, note_id: int) -> Optional[Dict[str, Any]]:
    return ctx.sql.query_one(
        """
        SELECT id, campaign_id, discord_srv_id, title, body, author_user_id,
               created_at, updated_at
          FROM dnd_dm_notes
         WHERE id = %s AND discord_srv_id = %s
        """,
        [int(note_id), int(ctx.server_id)],
    )


def list_notes_for_campaign(
    ctx, campaign_id: int, *, limit: int = 25
) -> List[Dict[str, Any]]:
    return ctx.sql.query(
        """
        SELECT id, title, body, author_user_id, updated_at
          FROM dnd_dm_notes
         WHERE campaign_id = %s AND discord_srv_id = %s
         ORDER BY updated_at DESC
         LIMIT %s
        """,
        [int(campaign_id), int(ctx.server_id), int(limit)],
    )
