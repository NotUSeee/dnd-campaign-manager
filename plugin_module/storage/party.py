"""Party roster. Soft-delete by setting is_active=FALSE to preserve attendance history."""
from typing import Any, Dict, List, Optional


def add_member(
    ctx,
    *,
    campaign_id: int,
    user_id: str,
    character_name: str = "",
    character_class: str = "",
    character_level: Optional[int] = None,
) -> int:
    return ctx.sql.execute(
        """
        INSERT INTO dnd_party_members
            (campaign_id, user_id, character_name, character_class, character_level, is_active)
        VALUES (%s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (campaign_id, user_id) DO UPDATE
            SET character_name = EXCLUDED.character_name,
                character_class = EXCLUDED.character_class,
                character_level = EXCLUDED.character_level,
                is_active = TRUE
        """,
        [
            int(campaign_id),
            int(user_id),
            str(character_name)[:120] if character_name else None,
            str(character_class)[:80] if character_class else None,
            int(character_level) if character_level else None,
        ],
    )


def remove_member(ctx, *, campaign_id: int, user_id: str) -> int:
    """Soft-delete — keeps the row so historical attendance still resolves."""
    return ctx.sql.execute(
        """
        UPDATE dnd_party_members SET is_active = FALSE
         WHERE campaign_id = %s AND user_id = %s
        """,
        [int(campaign_id), int(user_id)],
    )


def list_active_party(ctx, campaign_id: int) -> List[Dict[str, Any]]:
    return ctx.sql.query(
        """
        SELECT user_id, character_name, character_class, character_level, joined_at
          FROM dnd_party_members
         WHERE campaign_id = %s AND is_active = TRUE
         ORDER BY joined_at
        """,
        [int(campaign_id)],
    )


def get_member(ctx, *, campaign_id: int, user_id: str) -> Optional[Dict[str, Any]]:
    return ctx.sql.query_one(
        """
        SELECT user_id, character_name, character_class, character_level,
               is_active, joined_at
          FROM dnd_party_members
         WHERE campaign_id = %s AND user_id = %s
        """,
        [int(campaign_id), int(user_id)],
    )
