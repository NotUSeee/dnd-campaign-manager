"""/quest add | update | list handlers."""
from typing import Any, Dict, Optional

from plugin_module import plugin
from plugin_module.constants import CUSTOM_ID_PREFIX, INTERACTION_TYPE_MODAL_SUBMIT, MODAL_TITLE_MAX
from plugin_module.core import ids, permissions
from plugin_module.core.option_reader import (
    get_invoking_user_id,
    get_modal_value,
    get_option_int,
    get_option_str,
    get_subcommand,
)
from plugin_module.storage import campaigns as st_campaigns
from plugin_module.storage import quests as st_quests
from plugin_module.ui import components as ui_components
from plugin_module.ui import embeds as ui_embeds
from plugin_module.ui import modals as ui_modals


@plugin.on_slash_command("quest")
def handle_quest(ctx, event):
    sub = get_subcommand(event)
    if sub == "add":
        return _quest_add(ctx, event)
    if sub == "update":
        return _quest_update(ctx, event)
    if sub == "list":
        return _quest_list(ctx, event)
    ctx.interaction.respond(content="Unknown subcommand.", ephemeral=True)


# ── /quest add ───────────────────────────────────────────────────────────


def _quest_add(ctx, event):
    campaign_id = get_option_int(event, "campaign_id")
    campaign = _resolve_campaign(
        ctx, event, campaign_id,
        picker_target=ids.PICKER_CAMPAIGN_FOR_QUEST_ADD,
        prompt="Pick the campaign to add a quest to:",
    )
    if not campaign:
        return
    _show_visibility_picker(ctx, event, int(campaign["id"]))


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_CAMPAIGN_FOR_QUEST_ADD}")
def handle_quest_camp_picker(ctx, event):
    campaign_id = _picked_id(event)
    if not campaign_id:
        return
    _show_visibility_picker(ctx, event, campaign_id)


def _show_visibility_picker(ctx, event, campaign_id: int):
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    ctx.interaction.respond(
        content="Who can see this quest?",
        components=ui_components.visibility_picker("quest_add", campaign_id, allow_partial=False),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.VIS_PREFIX}quest_add:")
def handle_quest_vis_btn(ctx, event):
    parsed = ids.parse_visibility_btn_id(event.get("custom_id") or "")
    if not parsed:
        return
    _target, visibility, campaign_id = parsed
    if visibility not in ("public", "dm_only"):
        ctx.interaction.respond(content="Invalid visibility.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    ctx.interaction.send_modal(
        title=f"Add quest — {campaign['name']}"[:MODAL_TITLE_MAX],
        custom_id=ids.modal_quest_add_id(campaign_id, visibility),
        fields=ui_modals.quest_add_fields(),
    )


@plugin.on_event("interaction_create")
def handle_quest_add_modal(ctx, event):
    if event.get("interaction_type") != INTERACTION_TYPE_MODAL_SUBMIT:
        return
    parsed = ids.parse_modal_quest_add(event.get("custom_id") or "")
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
    title = get_modal_value(event, "title")
    description = get_modal_value(event, "description")
    if not title:
        ctx.interaction.respond(content="Title is required.", ephemeral=True)
        return
    quest = st_quests.create_quest(
        ctx,
        campaign_id=campaign_id,
        title=title,
        description=description,
        visibility=visibility,
        added_by_user_id=get_invoking_user_id(event),
    )
    if not quest:
        ctx.interaction.respond(content="Failed to add quest.", ephemeral=True)
        return
    ctx.interaction.respond(embeds=[ui_embeds.quest_added_embed(quest)], ephemeral=True)


# ── /quest update ────────────────────────────────────────────────────────


def _quest_update(ctx, event):
    quest_id = get_option_int(event, "quest_id")
    if quest_id:
        _send_quest_update_modal(ctx, event, quest_id)
        return
    # Picker: open quests across all campaigns the user can manage
    rows = ctx.sql.query(
        """
        SELECT q.id, q.title, q.status, q.visibility, q.campaign_id, c.name AS campaign_name
          FROM dnd_quests q
          JOIN dnd_campaigns c ON c.id = q.campaign_id
         WHERE q.discord_srv_id = %s AND q.status = 'active'
         ORDER BY q.updated_at DESC LIMIT 25
        """,
        [int(ctx.server_id)],
    )
    if not rows:
        ctx.interaction.respond(content="No active quests to update.", ephemeral=True)
        return
    ctx.interaction.respond(
        content="Pick the quest to update:",
        components=ui_components.quest_picker(
            ids.PICKER_QUEST_FOR_UPDATE, rows, placeholder="Pick a quest…"
        ),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_QUEST_FOR_UPDATE}")
def handle_quest_update_picker(ctx, event):
    quest_id = _picked_id(event)
    if not quest_id:
        return
    _send_quest_update_modal(ctx, event, quest_id)


def _send_quest_update_modal(ctx, event, quest_id: int):
    quest = st_quests.get_quest(ctx, quest_id)
    if not quest:
        ctx.interaction.respond(content="Quest not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(quest["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(quest["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    ctx.interaction.send_modal(
        title=f"Update — {str(quest['title'])[:30]}"[:MODAL_TITLE_MAX],
        custom_id=ids.modal_quest_update_id(quest_id),
        fields=ui_modals.quest_update_fields(current_status=str(quest.get("status") or "active")),
    )


@plugin.on_event("interaction_create")
def handle_quest_update_modal(ctx, event):
    if event.get("interaction_type") != INTERACTION_TYPE_MODAL_SUBMIT:
        return
    quest_id = ids.parse_modal_quest_update(event.get("custom_id") or "")
    if quest_id is None:
        return
    quest = st_quests.get_quest(ctx, quest_id)
    if not quest:
        ctx.interaction.respond(content="Quest not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(quest["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(quest["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    update_text = get_modal_value(event, "update_text")
    new_status = (get_modal_value(event, "new_status") or "").lower().strip()
    if not update_text:
        ctx.interaction.respond(content="Update text is required.", ephemeral=True)
        return
    st_quests.append_update(
        ctx, quest_id=quest_id, update_text=update_text,
        author_user_id=get_invoking_user_id(event),
    )
    if new_status and new_status in st_quests.VALID_STATUSES:
        st_quests.update_quest_status(ctx, quest_id, new_status)
    refreshed = st_quests.get_quest(ctx, quest_id) or quest
    ctx.interaction.respond(
        embeds=[ui_embeds.quest_updated_embed(refreshed, update_text)],
        ephemeral=True,
    )


# ── /quest list ──────────────────────────────────────────────────────────


def _quest_list(ctx, event):
    campaign_id = get_option_int(event, "campaign_id")
    status = get_option_str(event, "status")
    campaign = _resolve_campaign(
        ctx, event, campaign_id,
        picker_target=ids.PICKER_CAMPAIGN_FOR_QUEST_ADD,  # reuse same picker target
        prompt="Pick a campaign to list quests for:",
    )
    if not campaign:
        return
    settings = st_campaigns.get_settings(ctx, int(campaign["id"])) or {}
    viewer_is_dm = permissions.can_manage_campaign(event, campaign, settings)

    # When quest_log_public is False, the entire quest log is DM-only —
    # players see nothing at all (not just dm_only-tagged quests).
    if not viewer_is_dm and not bool(settings.get("quest_log_public", True)):
        ctx.interaction.respond(
            embeds=[ui_embeds.info_embed(
                f"📜 Quest log — {campaign['name']}",
                "This campaign's quest log is set to DM-only. Ask the DM for an update.",
            )],
            ephemeral=True,
        )
        return

    quests = st_quests.list_quests_for_campaign(
        ctx, int(campaign["id"]),
        status=status if status in st_quests.VALID_STATUSES else None,
        include_dm_only=viewer_is_dm,  # never show DM-only entries to players
        limit=100,
    )
    ctx.interaction.respond(
        embeds=[ui_embeds.quest_list_embed(
            campaign, quests,
            viewer_is_dm=viewer_is_dm,
            status_filter=status if status in st_quests.VALID_STATUSES else None,
        )],
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
