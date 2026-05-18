"""Campaigns + 1:1 campaign_settings CRUD."""
from typing import Any, Dict, List, Optional


def create_campaign(
    ctx,
    *,
    name: str,
    owner_user_id: str,
    party_name: str = "",
    system: str = "D&D 5e",
    description: str = "",
    timezone: str = "UTC",
) -> Optional[Dict[str, Any]]:
    """Insert a campaign + default settings row. Returns the new campaign dict, or None on conflict."""
    rows = ctx.sql.query(
        """
        INSERT INTO dnd_campaigns
            (discord_srv_id, name, party_name, system, description, timezone, owner_user_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
        RETURNING id, discord_srv_id, name, party_name, system, description,
                  timezone, owner_user_id, status, created_at, updated_at
        """,
        [
            int(ctx.server_id),
            str(name)[:200],
            str(party_name)[:200] if party_name else None,
            str(system)[:80] if system else "D&D 5e",
            str(description)[:2000] if description else None,
            str(timezone)[:80] if timezone else "UTC",
            int(owner_user_id),
        ],
    )
    if not rows:
        return None
    campaign = rows[0]
    ctx.sql.execute(
        """
        INSERT INTO dnd_campaign_settings (campaign_id) VALUES (%s)
        ON CONFLICT (campaign_id) DO NOTHING
        """,
        [int(campaign["id"])],
    )
    return campaign


def get_campaign(ctx, campaign_id: int) -> Optional[Dict[str, Any]]:
    return ctx.sql.query_one(
        """
        SELECT id, discord_srv_id, name, party_name, system, description,
               timezone, owner_user_id, status, created_at, updated_at
          FROM dnd_campaigns
         WHERE id = %s AND discord_srv_id = %s
        """,
        [int(campaign_id), int(ctx.server_id)],
    )


def list_campaigns_for_server(ctx, *, include_archived: bool = False) -> List[Dict[str, Any]]:
    if include_archived:
        sql = """
            SELECT id, name, party_name, system, owner_user_id, status, timezone
              FROM dnd_campaigns
             WHERE discord_srv_id = %s
             ORDER BY (status = 'active') DESC, name
        """
        return ctx.sql.query(sql, [int(ctx.server_id)])
    return ctx.sql.query(
        """
        SELECT id, name, party_name, system, owner_user_id, status, timezone
          FROM dnd_campaigns
         WHERE discord_srv_id = %s AND status <> 'archived'
         ORDER BY name
        """,
        [int(ctx.server_id)],
    )


def get_settings(ctx, campaign_id: int) -> Optional[Dict[str, Any]]:
    return ctx.sql.query_one(
        """
        SELECT campaign_id, default_day_of_week, default_time_local,
               announce_channel_id, recap_channel_id, reminder_channel_id,
               dm_role_id, player_role_id, reminder_offsets_minutes,
               rsvp_required, maybe_allowed, alternate_times_allowed,
               recap_draft_first, quest_log_public, npc_default_visibility,
               ping_on_reminders, updated_at
          FROM dnd_campaign_settings
         WHERE campaign_id = %s
        """,
        [int(campaign_id)],
    )


def update_settings(ctx, campaign_id: int, fields: Dict[str, Any]) -> int:
    """Sparse update of campaign settings. Returns affected row count."""
    allowed = {
        "default_day_of_week", "default_time_local",
        "announce_channel_id", "recap_channel_id", "reminder_channel_id",
        "dm_role_id", "player_role_id", "reminder_offsets_minutes",
        "rsvp_required", "maybe_allowed", "alternate_times_allowed",
        "recap_draft_first", "quest_log_public", "npc_default_visibility",
        "ping_on_reminders",
    }
    sets: List[str] = []
    params: List[Any] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        sets.append(f"{key} = %s")
        params.append(value)
    if not sets:
        return 0
    sets.append("updated_at = NOW()")
    params.append(int(campaign_id))
    sql = f"UPDATE dnd_campaign_settings SET {', '.join(sets)} WHERE campaign_id = %s"
    return ctx.sql.execute(sql, params)


def update_campaign_fields(ctx, campaign_id: int, fields: Dict[str, Any]) -> int:
    allowed = {"name", "party_name", "system", "description", "timezone", "status"}
    sets: List[str] = []
    params: List[Any] = []
    for key, value in fields.items():
        if key not in allowed:
            continue
        sets.append(f"{key} = %s")
        params.append(value)
    if not sets:
        return 0
    sets.append("updated_at = NOW()")
    params.extend([int(campaign_id), int(ctx.server_id)])
    sql = (
        f"UPDATE dnd_campaigns SET {', '.join(sets)} "
        "WHERE id = %s AND discord_srv_id = %s"
    )
    return ctx.sql.execute(sql, params)


def archive_campaign(ctx, campaign_id: int) -> int:
    return ctx.sql.execute(
        """
        UPDATE dnd_campaigns SET status = 'archived', updated_at = NOW()
         WHERE id = %s AND discord_srv_id = %s
        """,
        [int(campaign_id), int(ctx.server_id)],
    )


def get_default_campaign(ctx) -> Optional[Dict[str, Any]]:
    """If the server has exactly one active campaign, return it. Otherwise None."""
    rows = ctx.sql.query(
        """
        SELECT id, discord_srv_id, name, party_name, system, description,
               timezone, owner_user_id, status
          FROM dnd_campaigns
         WHERE discord_srv_id = %s AND status = 'active'
         LIMIT 2
        """,
        [int(ctx.server_id)],
    )
    if len(rows) == 1:
        return rows[0]
    return None
