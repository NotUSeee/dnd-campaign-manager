"""/dmnotes add | list — DM-only, ephemeral replies ONLY.

Hard guarantee: this module never calls ctx.discord.send_message. Every
response goes through ctx.interaction.respond(ephemeral=True) or
ctx.interaction.followup(ephemeral=True). Test enforced.
"""
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
from plugin_module.storage import notes as st_notes
from plugin_module.ui import components as ui_components
from plugin_module.ui import embeds as ui_embeds
from plugin_module.ui import modals as ui_modals


@plugin.on_slash_command("dmnotes")
def handle_dmnotes(ctx, event):
    sub = get_subcommand(event)
    if sub == "add":
        return _dmnote_add(ctx, event)
    if sub == "list":
        return _dmnote_list(ctx, event)
    ctx.interaction.respond(content="Unknown subcommand.", ephemeral=True)


def _dmnote_add(ctx, event):
    campaign = _resolve_campaign(
        ctx, event, get_option_int(event, "campaign_id"),
        picker_target=ids.PICKER_CAMPAIGN_FOR_DMNOTE_ADD,
        prompt="Pick the campaign to add a DM note to:",
    )
    if not campaign:
        return
    settings = st_campaigns.get_settings(ctx, int(campaign["id"])) or {}
    if not permissions.require_can_view_dm_notes(ctx, event, campaign, settings):
        return
    ctx.interaction.send_modal(
        title=f"DM note — {campaign['name']}"[:MODAL_TITLE_MAX],
        custom_id=ids.modal_dmnote_add_id(int(campaign["id"])),
        fields=ui_modals.dmnote_add_fields(),
    )


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_CAMPAIGN_FOR_DMNOTE_ADD}")
def handle_dmnote_add_picker(ctx, event):
    campaign_id = _picked_id(event)
    if not campaign_id:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_view_dm_notes(ctx, event, campaign, settings):
        return
    ctx.interaction.send_modal(
        title=f"DM note — {campaign['name']}"[:MODAL_TITLE_MAX],
        custom_id=ids.modal_dmnote_add_id(campaign_id),
        fields=ui_modals.dmnote_add_fields(),
    )


@plugin.on_event("interaction_create")
def handle_dmnote_add_modal(ctx, event):
    if event.get("interaction_type") != INTERACTION_TYPE_MODAL_SUBMIT:
        return
    campaign_id = ids.parse_modal_dmnote_add(event.get("custom_id") or "")
    if campaign_id is None:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_view_dm_notes(ctx, event, campaign, settings):
        return
    title = get_modal_value(event, "title")
    body = get_modal_value(event, "body")
    if not title or not body:
        ctx.interaction.respond(
            content="Title and body are both required.", ephemeral=True
        )
        return
    note = st_notes.create_note(
        ctx, campaign_id=campaign_id, title=title, body=body,
        author_user_id=get_invoking_user_id(event),
    )
    if not note:
        ctx.interaction.respond(content="Failed to save the note.", ephemeral=True)
        return
    ctx.interaction.respond(
        embeds=[ui_embeds.dmnote_added_embed(note)],
        ephemeral=True,
    )


def _dmnote_list(ctx, event):
    campaign = _resolve_campaign(
        ctx, event, get_option_int(event, "campaign_id"),
        picker_target=ids.PICKER_CAMPAIGN_FOR_DMNOTE_LIST,
        prompt="Pick the campaign whose DM notes to list:",
    )
    if not campaign:
        return
    settings = st_campaigns.get_settings(ctx, int(campaign["id"])) or {}
    if not permissions.require_can_view_dm_notes(ctx, event, campaign, settings):
        return
    notes = st_notes.list_notes_for_campaign(ctx, int(campaign["id"]))
    ctx.interaction.respond(
        embeds=[ui_embeds.dmnote_list_embed(campaign, notes)],
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_CAMPAIGN_FOR_DMNOTE_LIST}")
def handle_dmnote_list_picker(ctx, event):
    campaign_id = _picked_id(event)
    if not campaign_id:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_view_dm_notes(ctx, event, campaign, settings):
        return
    notes = st_notes.list_notes_for_campaign(ctx, campaign_id)
    ctx.interaction.respond(
        embeds=[ui_embeds.dmnote_list_embed(campaign, notes)],
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
