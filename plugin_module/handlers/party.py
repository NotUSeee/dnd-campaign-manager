"""/party add | remove | list handlers."""
from typing import Any, Dict, Optional

from plugin_module import plugin
from plugin_module.core import ids, permissions
from plugin_module.core.option_reader import (
    get_option_int,
    get_option_str,
    get_option_user_id,
    get_subcommand,
)
from plugin_module.storage import campaigns as st_campaigns
from plugin_module.storage import party as st_party
from plugin_module.ui import components as ui_components
from plugin_module.ui import embeds as ui_embeds


@plugin.on_slash_command("party")
def handle_party(ctx, event):
    sub = get_subcommand(event)
    if sub == "add":
        return _party_add(ctx, event)
    if sub == "remove":
        return _party_remove(ctx, event)
    if sub == "list":
        return _party_list(ctx, event)
    ctx.interaction.respond(content="Unknown subcommand.", ephemeral=True)


def _party_add(ctx, event):
    campaign = _resolve_campaign(
        ctx, event, get_option_int(event, "campaign_id"),
        picker_target=ids.PICKER_CAMPAIGN_FOR_PARTY,
        prompt="Pick the campaign to add a player to:",
    )
    if not campaign:
        return
    settings = st_campaigns.get_settings(ctx, int(campaign["id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    user_id = get_option_user_id(event, "user")
    if not user_id:
        ctx.interaction.respond(content="User is required.", ephemeral=True)
        return
    character_name = get_option_str(event, "character_name") or ""
    st_party.add_member(
        ctx, campaign_id=int(campaign["id"]), user_id=user_id,
        character_name=character_name,
    )
    ctx.interaction.respond(
        embeds=[ui_embeds.success_embed(
            "Player added",
            f"<@{user_id}> joined **{campaign['name']}**" +
            (f" as **{character_name}**." if character_name else "."),
        )],
        ephemeral=True,
    )


def _party_remove(ctx, event):
    campaign = _resolve_campaign(
        ctx, event, get_option_int(event, "campaign_id"),
        picker_target=ids.PICKER_CAMPAIGN_FOR_PARTY,
        prompt="Pick the campaign to remove a player from:",
    )
    if not campaign:
        return
    settings = st_campaigns.get_settings(ctx, int(campaign["id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    user_id = get_option_user_id(event, "user")
    if not user_id:
        ctx.interaction.respond(content="User is required.", ephemeral=True)
        return
    affected = st_party.remove_member(ctx, campaign_id=int(campaign["id"]), user_id=user_id)
    if not affected:
        ctx.interaction.respond(
            content=f"<@{user_id}> isn't in the party.", ephemeral=True
        )
        return
    ctx.interaction.respond(
        embeds=[ui_embeds.success_embed(
            "Player removed",
            f"<@{user_id}> left **{campaign['name']}**. (Attendance history preserved.)",
        )],
        ephemeral=True,
    )


def _party_list(ctx, event):
    campaign = _resolve_campaign(
        ctx, event, get_option_int(event, "campaign_id"),
        picker_target=ids.PICKER_CAMPAIGN_FOR_PARTY,
        prompt="Pick a campaign to list the party of:",
    )
    if not campaign:
        return
    members = st_party.list_active_party(ctx, int(campaign["id"]))
    ctx.interaction.respond(
        embeds=[ui_embeds.party_roster_embed(campaign, members)],
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_CAMPAIGN_FOR_PARTY}")
def handle_party_picker(ctx, event):
    campaign_id = _picked_id(event)
    if not campaign_id:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    members = st_party.list_active_party(ctx, campaign_id)
    ctx.interaction.respond(
        embeds=[ui_embeds.party_roster_embed(campaign, members)],
        ephemeral=True,
    )


# ── helpers ──────────────────────────────────────────────────────────────


def _resolve_campaign(
    ctx, event, campaign_id: Optional[int], *, picker_target: str, prompt: str
) -> Optional[Dict[str, Any]]:
    if campaign_id:
        campaign = st_campaigns.get_campaign(ctx, campaign_id)
        if campaign:
            return campaign
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return None
    all_campaigns = st_campaigns.list_campaigns_for_server(ctx)
    if not all_campaigns:
        ctx.interaction.respond(
            content="No campaigns yet. Run `/campaign create` first.", ephemeral=True
        )
        return None
    if len(all_campaigns) == 1:
        return st_campaigns.get_campaign(ctx, int(all_campaigns[0]["id"]))
    ctx.interaction.respond(
        content=prompt,
        components=ui_components.campaign_picker(picker_target, all_campaigns),
        ephemeral=True,
    )
    return None


def _picked_id(event) -> Optional[int]:
    values = event.get("values") or []
    if not values:
        return None
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return None
