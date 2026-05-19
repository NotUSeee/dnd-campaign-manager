"""Quest log + per-quest update history."""
from typing import Any, Dict, List, Optional


VALID_STATUSES = ("active", "completed", "failed", "abandoned")
VALID_VISIBILITIES = ("public", "dm_only")


def create_quest(
    ctx,
    *,
    campaign_id: int,
    title: str,
    description: str,
    visibility: str,
    added_by_user_id: str,
) -> Optional[Dict[str, Any]]:
    if visibility not in VALID_VISIBILITIES:
        visibility = "public"
    affected = ctx.sql.execute(
        """
        INSERT INTO dnd_quests (
            campaign_id, discord_srv_id, title, description,
            visibility, added_by_user_id
        )
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        [
            int(campaign_id),
            int(ctx.server_id),
            str(title)[:200],
            str(description)[:2000] if description else None,
            visibility,
            int(added_by_user_id),
        ],
    )
    if not affected:
        return None
    return ctx.sql.query_one(
        """
        SELECT id, campaign_id, discord_srv_id, title, description,
               status, visibility, added_by_user_id, created_at, updated_at
          FROM dnd_quests
         WHERE campaign_id = %s AND added_by_user_id = %s AND title = %s
         ORDER BY id DESC LIMIT 1
        """,
        [int(campaign_id), int(added_by_user_id), str(title)[:200]],
    )


def get_quest(ctx, quest_id: int) -> Optional[Dict[str, Any]]:
    return ctx.sql.query_one(
        """
        SELECT id, campaign_id, discord_srv_id, title, description, status,
               visibility, added_by_user_id, created_at, updated_at
          FROM dnd_quests
         WHERE id = %s AND discord_srv_id = %s
        """,
        [int(quest_id), int(ctx.server_id)],
    )


def list_quests_for_campaign(
    ctx,
    campaign_id: int,
    *,
    status: Optional[str] = None,
    include_dm_only: bool = False,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    where = ["campaign_id = %s", "discord_srv_id = %s"]
    params: List[Any] = [int(campaign_id), int(ctx.server_id)]
    if status and status in VALID_STATUSES:
        where.append("status = %s")
        params.append(status)
    if not include_dm_only:
        where.append("visibility = 'public'")
    params.append(int(limit))
    sql = f"""
        SELECT id, title, description, status, visibility, added_by_user_id,
               updated_at
          FROM dnd_quests
         WHERE {' AND '.join(where)}
         ORDER BY (status = 'active') DESC, updated_at DESC
         LIMIT %s
    """
    return ctx.sql.query(sql, params)


def update_quest_status(ctx, quest_id: int, status: str) -> int:
    if status not in VALID_STATUSES:
        return 0
    return ctx.sql.execute(
        """
        UPDATE dnd_quests
           SET status = %s, updated_at = NOW()
         WHERE id = %s AND discord_srv_id = %s
        """,
        [status, int(quest_id), int(ctx.server_id)],
    )


def append_update(
    ctx, *, quest_id: int, update_text: str, author_user_id: str
) -> Optional[Dict[str, Any]]:
    affected = ctx.sql.execute(
        """
        INSERT INTO dnd_quest_updates (quest_id, update_text, author_user_id)
        VALUES (%s, %s, %s)
        """,
        [int(quest_id), str(update_text)[:2000], int(author_user_id)],
    )
    if not affected:
        return None
    ctx.sql.execute(
        "UPDATE dnd_quests SET updated_at = NOW() WHERE id = %s", [int(quest_id)]
    )
    return ctx.sql.query_one(
        """
        SELECT id, quest_id, update_text, author_user_id, created_at
          FROM dnd_quest_updates
         WHERE quest_id = %s AND author_user_id = %s
         ORDER BY id DESC LIMIT 1
        """,
        [int(quest_id), int(author_user_id)],
    )


def list_updates_for_quest(ctx, quest_id: int, *, limit: int = 25) -> List[Dict[str, Any]]:
    return ctx.sql.query(
        """
        SELECT id, update_text, author_user_id, created_at
          FROM dnd_quest_updates
         WHERE quest_id = %s
         ORDER BY created_at DESC
         LIMIT %s
        """,
        [int(quest_id), int(limit)],
    )
