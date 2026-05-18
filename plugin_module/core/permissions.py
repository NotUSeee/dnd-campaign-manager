"""Permission predicates and gates.

All gates operate on the raw event dict (so they're pure-functional and
trivially unit-testable with `make_event(...)`). Composed `require_*`
helpers send an ephemeral denial reply and return False — the caller
returns immediately on False.
"""
from typing import Any, Dict, Optional

from plugin_module.constants import DISCORD_PERMISSION_ADMINISTRATOR


def _member(event: Dict[str, Any]) -> Dict[str, Any]:
    return event.get("member") or {}


def _user_id(event: Dict[str, Any]) -> str:
    user = _member(event).get("user") or {}
    return str(user.get("id") or event.get("user_id") or "")


def _member_role_ids(event: Dict[str, Any]) -> set:
    raw = _member(event).get("roles") or []
    return {str(r) for r in raw}


def is_server_admin(event: Dict[str, Any]) -> bool:
    """True if the invoking member has Discord's ADMINISTRATOR bit."""
    perms_str = _member(event).get("permissions") or "0"
    try:
        return bool(int(perms_str) & DISCORD_PERMISSION_ADMINISTRATOR)
    except (ValueError, TypeError):
        return False


def is_campaign_owner(event: Dict[str, Any], campaign: Optional[Dict[str, Any]]) -> bool:
    """True if the invoking user is the campaign owner_user_id."""
    if not campaign:
        return False
    owner = campaign.get("owner_user_id")
    if owner is None:
        return False
    return str(owner) == _user_id(event)


def is_dm_role(event: Dict[str, Any], settings: Optional[Dict[str, Any]]) -> bool:
    """True if the invoking member holds the campaign's configured dm_role_id.

    If no DM role is configured, returns False — server admin or campaign
    owner remain the management paths.
    """
    if not settings:
        return False
    role_id = settings.get("dm_role_id")
    if not role_id:
        return False
    return str(role_id) in _member_role_ids(event)


def is_player(event: Dict[str, Any], settings: Optional[Dict[str, Any]]) -> bool:
    """True if the invoking member holds the player role, or no player role configured."""
    if not settings:
        return True
    role_id = settings.get("player_role_id")
    if not role_id:
        return True
    return str(role_id) in _member_role_ids(event)


def can_manage_campaign(
    event: Dict[str, Any],
    campaign: Optional[Dict[str, Any]],
    settings: Optional[Dict[str, Any]],
) -> bool:
    """Composed predicate: admin OR campaign owner OR DM role."""
    return (
        is_server_admin(event)
        or is_campaign_owner(event, campaign)
        or is_dm_role(event, settings)
    )


def can_create_campaigns(event: Dict[str, Any]) -> bool:
    """Anyone with admin rights can bootstrap a campaign. (No prior settings exist.)

    Servers that want stricter rules can rely on Discord's command-level
    permissions UI to restrict the slash command itself.
    """
    return is_server_admin(event)


def can_view_dm_notes(
    event: Dict[str, Any],
    campaign: Optional[Dict[str, Any]],
    settings: Optional[Dict[str, Any]],
) -> bool:
    """DM-only by intent — campaign owners and DM-role holders only.

    Server admins are also permitted because they can read anything via
    Discord regardless, so blocking them adds friction without security gain.
    """
    return can_manage_campaign(event, campaign, settings)


# ── Interaction-aware require_* helpers ───────────────────────────────────


def _deny(ctx, message: str) -> bool:
    try:
        ctx.interaction.respond(content=message, ephemeral=True)
    except Exception:
        pass
    return False


def require_server_admin(ctx, event) -> bool:
    if is_server_admin(event):
        return True
    return _deny(
        ctx,
        "Only server admins can do that. Ask a moderator with Administrator permission.",
    )


def require_can_manage(ctx, event, campaign, settings) -> bool:
    if can_manage_campaign(event, campaign, settings):
        return True
    return _deny(
        ctx,
        "You don't have permission to manage this campaign. Ask the DM or a server admin.",
    )


def require_can_view_dm_notes(ctx, event, campaign, settings) -> bool:
    if can_view_dm_notes(event, campaign, settings):
        return True
    return _deny(ctx, "DM-only. Only the DM or a server admin can see these notes.")
