"""/npc add | list handlers (visibility-before-modal)."""
from typing import Any, Dict, Optional

from plugin_module import plugin
from plugin_module.constants import INTERACTION_TYPE_MODAL_SUBMIT, MODAL_TITLE_MAX
from plugin_module.core import ids, permissions
from plugin_module.core.option_reader import (
    get_invoking_user_id,
    get_modal_value,
    get_option_int,
    get_subcommand,
)
from plugin_module.storage import campaigns as st_campaigns
from plugin_module.storage import npcs as st_npcs
from plugin_module.ui import components as ui_components
from plugin_module.ui import embeds as ui_embeds
from plugin_module.ui import modals as ui_modals


@plugin.on_slash_command("npc")
def handle_npc(ctx, event):
    sub = get_subcommand(event)
    if sub == "add":
        return _npc_add(ctx, event)
    if sub == "list":
        return _npc_list(ctx, event)
    ctx.interaction.respond(content="Unknown subcommand.", ephemeral=True)


def _npc_add(ctx, event):
    campaign_id = get_option_int(event, "campaign_id")
    campaign = _resolve_campaign(
        ctx, event, campaign_id,
        picker_target=ids.PICKER_CAMPAIGN_FOR_NPC_ADD,
        prompt="Pick the campaign to add an NPC to:",
    )
    if not campaign:
        return
    settings = st_campaigns.get_settings(ctx, int(campaign["id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    default_vis = str(settings.get("npc_default_visibility") or "public")
    ctx.interaction.respond(
        content="What visibility should this NPC have?",
        components=ui_components.visibility_picker(
            "npc_add", int(campaign["id"]),
            allow_partial=True, default_visibility=default_vis,
        ),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_CAMPAIGN_FOR_NPC_ADD}")
def handle_npc_camp_picker(ctx, event):
    campaign_id = _picked_id(event)
    if not campaign_id:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    default_vis = str(settings.get("npc_default_visibility") or "public")
    ctx.interaction.respond(
        content="What visibility should this NPC have?",
        components=ui_components.visibility_picker(
            "npc_add", campaign_id,
            allow_partial=True, default_visibility=default_vis,
        ),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.VIS_PREFIX}npc_add:")
def handle_npc_vis_btn(ctx, event):
    parsed = ids.parse_visibility_btn_id(event.get("custom_id") or "")
    if not parsed:
        return
    _target, visibility, campaign_id = parsed
    if visibility not in st_npcs.VALID_VISIBILITIES:
        ctx.interaction.respond(content="Invalid visibility.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    ctx.interaction.send_modal(
        title=f"Add NPC — {campaign['name']}"[:MODAL_TITLE_MAX],
        custom_id=ids.modal_npc_add_id(campaign_id, visibility),
        fields=ui_modals.npc_add_fields(),
    )


@plugin.on_event("interaction_create")
def handle_npc_add_modal(ctx, event):
    if event.get("interaction_type") != INTERACTION_TYPE_MODAL_SUBMIT:
        return
    parsed = ids.parse_modal_npc_add(event.get("custom_id") or "")
    if not parsed:
        return
    campaign_id, visibility = parsed
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    name = get_modal_value(event, "name")
    if not name:
        ctx.interaction.respond(content="Name is required.", ephemeral=True)
        return
    npc = st_npcs.create_npc(
        ctx,
        campaign_id=campaign_id,
        name=name,
        role=get_modal_value(event, "role"),
        location=get_modal_value(event, "location"),
        public_notes=get_modal_value(event, "public_notes"),
        secret_notes=get_modal_value(event, "secret_notes"),
        visibility=visibility,
        added_by_user_id=get_invoking_user_id(event),
    )
    if not npc:
        ctx.interaction.respond(content="Failed to add NPC.", ephemeral=True)
        return
    ctx.interaction.respond(embeds=[ui_embeds.npc_added_embed(npc)], ephemeral=True)


def _npc_list(ctx, event):
    campaign_id = get_option_int(event, "campaign_id")
    campaign = _resolve_campaign(
        ctx, event, campaign_id,
        picker_target=ids.PICKER_CAMPAIGN_FOR_NPC_ADD,
        prompt="Pick a campaign to list NPCs for:",
    )
    if not campaign:
        return
    settings = st_campaigns.get_settings(ctx, int(campaign["id"])) or {}
    viewer_is_dm = permissions.can_manage_campaign(event, campaign, settings)
    npcs = st_npcs.list_npcs_for_campaign(ctx, int(campaign["id"]), viewer_is_dm=viewer_is_dm)
    ctx.interaction.respond(
        embeds=[ui_embeds.npc_list_embed(campaign, npcs, viewer_is_dm=viewer_is_dm)],
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
