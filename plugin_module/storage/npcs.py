"""NPC storage with three visibility tiers (public / partial / dm_only)."""
from typing import Any, Dict, List, Optional


VALID_VISIBILITIES = ("public", "partial", "dm_only")


def create_npc(
    ctx,
    *,
    campaign_id: int,
    name: str,
    role: str,
    location: str,
    public_notes: str,
    secret_notes: str,
    visibility: str,
    added_by_user_id: str,
) -> Optional[Dict[str, Any]]:
    if visibility not in VALID_VISIBILITIES:
        visibility = "public"
    affected = ctx.sql.execute(
        """
        INSERT INTO dnd_npcs (
            campaign_id, discord_srv_id, name, role, location,
            public_notes, secret_notes, visibility, added_by_user_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        [
            int(campaign_id),
            int(ctx.server_id),
            str(name)[:200],
            str(role)[:200] if role else None,
            str(location)[:200] if location else None,
            str(public_notes)[:2000] if public_notes else None,
            str(secret_notes)[:2000] if secret_notes else None,
            visibility,
            int(added_by_user_id),
        ],
    )
    if not affected:
        return None
    return ctx.sql.query_one(
        """
        SELECT id, campaign_id, discord_srv_id, name, role, location,
               public_notes, secret_notes, visibility, added_by_user_id,
               created_at, updated_at
          FROM dnd_npcs
         WHERE campaign_id = %s AND added_by_user_id = %s AND name = %s
         ORDER BY id DESC LIMIT 1
        """,
        [int(campaign_id), int(added_by_user_id), str(name)[:200]],
    )


def get_npc(ctx, npc_id: int) -> Optional[Dict[str, Any]]:
    return ctx.sql.query_one(
        """
        SELECT id, campaign_id, discord_srv_id, name, role, location,
               public_notes, secret_notes, visibility, added_by_user_id,
               created_at, updated_at
          FROM dnd_npcs
         WHERE id = %s AND discord_srv_id = %s
        """,
        [int(npc_id), int(ctx.server_id)],
    )


def list_npcs_for_campaign(
    ctx, campaign_id: int, *, viewer_is_dm: bool, limit: int = 25
) -> List[Dict[str, Any]]:
    """Lists NPCs filtered by visibility for the caller.

    - DM sees everything (including secret_notes).
    - Players see public + partial entries; partial entries omit secret_notes
      and public_notes longer than 200 chars get truncated.
    """
    if viewer_is_dm:
        rows = ctx.sql.query(
            """
            SELECT id, name, role, location, public_notes, secret_notes,
                   visibility, updated_at
              FROM dnd_npcs
             WHERE campaign_id = %s AND discord_srv_id = %s
             ORDER BY name
             LIMIT %s
            """,
            [int(campaign_id), int(ctx.server_id), int(limit)],
        )
        return rows

    rows = ctx.sql.query(
        """
        SELECT id, name, role, location, public_notes, visibility, updated_at
          FROM dnd_npcs
         WHERE campaign_id = %s AND discord_srv_id = %s
           AND visibility IN ('public','partial')
         ORDER BY name
         LIMIT %s
        """,
        [int(campaign_id), int(ctx.server_id), int(limit)],
    )
    # Strip secret data on partial-visibility entries
    sanitized: List[Dict[str, Any]] = []
    for r in rows:
        if r.get("visibility") == "partial":
            sanitized.append({
                "id": r["id"],
                "name": r["name"],
                "role": r.get("role"),
                "location": None,
                "public_notes": None,
                "visibility": "partial",
                "updated_at": r.get("updated_at"),
            })
        else:
            sanitized.append(r)
    return sanitized
