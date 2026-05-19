"""/campaign create | settings | info handlers."""
from typing import Any, Dict, Optional

from plugin_module import plugin
from plugin_module.constants import MODAL_TITLE_MAX
from plugin_module.core import ids, permissions
from plugin_module.core.option_reader import (
    get_invoking_user_id,
    get_modal_value,
    get_option_int,
    get_subcommand,
)
from plugin_module.core.time_util import validate_timezone
from plugin_module.storage import campaigns as st_campaigns
from plugin_module.storage import quests as st_quests
from plugin_module.storage import party as st_party
from plugin_module.storage import sessions as st_sessions
from plugin_module.ui import components as ui_components
from plugin_module.ui import embeds as ui_embeds
from plugin_module.ui import modals as ui_modals


@plugin.on_slash_command("campaign")
def handle_campaign(ctx, event):
    sub = get_subcommand(event)
    if sub == "create":
        return _campaign_create(ctx, event)
    if sub == "settings":
        return _campaign_settings(ctx, event)
    if sub == "info":
        return _campaign_info(ctx, event)
    # Diagnostic — if the heuristic still misses, log the raw shape so we
    # can see what Discord/discord.py actually delivered.
    try:
        ctx.log(
            f"/campaign: unknown subcommand sub={sub!r} options={event.get('options')!r}",
            level="warning", tags=["campaign", "dispatch"],
        )
    except Exception:
        pass
    ctx.interaction.respond(content="Unknown subcommand.", ephemeral=True)


# ── /campaign create ──────────────────────────────────────────────────────


def _campaign_create(ctx, event):
    if not permissions.can_create_campaigns(event):
        ctx.interaction.respond(
            content=("Only server admins can create new campaigns. "
                     "Ask a moderator with Administrator permission."),
            ephemeral=True,
        )
        return
    ctx.interaction.send_modal(
        title="Create campaign"[:MODAL_TITLE_MAX],
        custom_id=ids.MODAL_CAMPAIGN_CREATE,
        fields=ui_modals.campaign_create_fields(),
    )


@plugin.on_modal_submit(ids.MODAL_CAMPAIGN_CREATE)
def handle_campaign_create_submit(ctx, event):
    name = get_modal_value(event, "name")
    party_name = get_modal_value(event, "party_name")
    system = get_modal_value(event, "system") or "D&D 5e"
    description = get_modal_value(event, "description")
    timezone = get_modal_value(event, "timezone") or "UTC"
    user_id = get_invoking_user_id(event)

    if not name:
        ctx.interaction.respond(content="Campaign name is required.", ephemeral=True)
        return
    if not validate_timezone(timezone):
        ctx.interaction.respond(
            content=f"`{timezone}` isn't a recognized timezone. Try an IANA name like `America/New_York`.",
            ephemeral=True,
        )
        return

    campaign = st_campaigns.create_campaign(
        ctx,
        name=name,
        owner_user_id=user_id,
        party_name=party_name,
        system=system,
        description=description,
        timezone=timezone,
    )
    if not campaign:
        ctx.interaction.respond(
            content=f"A campaign named **{name}** already exists in this server.",
            ephemeral=True,
        )
        return
    ctx.interaction.respond(
        embeds=[ui_embeds.campaign_created_embed(campaign)],
        ephemeral=True,
    )
    ctx.log(
        f"Campaign '{name}' created (id={campaign['id']})",
        level="info",
        tags=["campaign", "create"],
        campaign_id=str(campaign["id"]),
    )


# ── /campaign settings ────────────────────────────────────────────────────


def _campaign_settings(ctx, event):
    campaign_id = get_option_int(event, "campaign_id")
    campaign = _resolve_campaign(
        ctx, event, campaign_id,
        picker_target=ids.PICKER_CAMPAIGN_FOR_SETTINGS,
        prompt="Pick the campaign whose settings you want to edit:",
    )
    if not campaign:
        return
    settings = st_campaigns.get_settings(ctx, int(campaign["id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    _show_settings_panel(ctx, campaign, settings)


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_CAMPAIGN_FOR_SETTINGS}")
def handle_settings_picker(ctx, event):
    campaign_id = _picked_id(event)
    if not campaign_id:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    _show_settings_panel(ctx, campaign, settings)


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_CAMPAIGN_FOR_INFO}")
def handle_info_picker(ctx, event):
    campaign_id = _picked_id(event)
    if not campaign_id:
        return
    _render_campaign_info(ctx, event, campaign_id)


def _show_settings_panel(ctx, campaign: Dict[str, Any], settings: Dict[str, Any]):
    """Render the settings summary embed + edit-button panel."""
    ctx.interaction.respond(
        embeds=[ui_embeds.campaign_settings_summary_embed(campaign, settings)],
        components=ui_components.settings_panel_components(int(campaign["id"])),
        ephemeral=True,
    )


# ── Edit-button handlers (one per section) ────────────────────────────────


@plugin.on_component(prefix=f"{ids.CUSTOM_ID_PREFIX}:settings_edit:")
def handle_settings_edit_button(ctx, event):
    parsed = ids.parse_settings_edit_btn(event.get("custom_id") or "")
    if not parsed:
        return
    section, campaign_id = parsed
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return

    title_prefix = f"Settings — {campaign['name']}"
    if section == "channels":
        ctx.interaction.send_modal(
            title=f"{title_prefix} · Channels"[:MODAL_TITLE_MAX],
            custom_id=ids.modal_settings_section_id("channels", campaign_id),
            fields=ui_modals.settings_channels_fields(settings),
        )
    elif section == "roles":
        ctx.interaction.send_modal(
            title=f"{title_prefix} · Roles"[:MODAL_TITLE_MAX],
            custom_id=ids.modal_settings_section_id("roles", campaign_id),
            fields=ui_modals.settings_roles_fields(settings),
        )
    elif section == "reminders":
        ctx.interaction.send_modal(
            title=f"{title_prefix} · Reminders"[:MODAL_TITLE_MAX],
            custom_id=ids.modal_settings_section_id("reminders", campaign_id),
            fields=ui_modals.settings_reminders_fields(settings),
        )
    elif section == "defaults":
        ctx.interaction.send_modal(
            title=f"{title_prefix} · Defaults"[:MODAL_TITLE_MAX],
            custom_id=ids.modal_settings_section_id("defaults", campaign_id),
            fields=ui_modals.settings_defaults_fields(settings),
        )
    elif section == "toggles":
        ctx.interaction.respond(
            content=f"**Toggles for {campaign['name']}** — click any toggle to flip it.",
            components=ui_components.toggles_panel_components(campaign_id, settings),
            ephemeral=True,
        )
    elif section == "npc_vis":
        current = str(settings.get("npc_default_visibility") or "public")
        ctx.interaction.respond(
            content=f"**Default NPC visibility for {campaign['name']}**",
            components=ui_components.npc_visibility_select(campaign_id, current=current),
            ephemeral=True,
        )
    else:
        ctx.interaction.respond(content="Unknown settings section.", ephemeral=True)


# ── Section modal submits ─────────────────────────────────────────────────


@plugin.on_event("interaction_create")
def handle_settings_modal_dispatch(ctx, event):
    """Routes all `dnd_v1:modal:settings_*:<cid>` modal submits."""
    from plugin_module.constants import INTERACTION_TYPE_MODAL_SUBMIT
    if event.get("interaction_type") != INTERACTION_TYPE_MODAL_SUBMIT:
        return
    parsed = ids.parse_modal_settings_section(event.get("custom_id") or "")
    if not parsed:
        return
    section, campaign_id = parsed
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return

    if section == "channels":
        st_campaigns.update_settings(ctx, campaign_id, {
            "announce_channel_id": _parse_id(get_modal_value(event, "announce_channel_id")),
            "recap_channel_id":    _parse_id(get_modal_value(event, "recap_channel_id")),
            "reminder_channel_id": _parse_id(get_modal_value(event, "reminder_channel_id")),
        })
    elif section == "roles":
        st_campaigns.update_settings(ctx, campaign_id, {
            "dm_role_id":     _parse_id(get_modal_value(event, "dm_role_id")),
            "player_role_id": _parse_id(get_modal_value(event, "player_role_id")),
        })
    elif section == "reminders":
        offsets = _parse_offsets(get_modal_value(event, "reminder_offsets"))
        if not offsets:
            ctx.interaction.respond(
                content="At least one reminder offset is required (e.g. `15`).",
                ephemeral=True,
            )
            return
        st_campaigns.update_settings(ctx, campaign_id, {"reminder_offsets_minutes": offsets})
    elif section == "defaults":
        dow_raw = get_modal_value(event, "default_day_of_week")
        time_raw = get_modal_value(event, "default_time_local")
        update_fields: Dict[str, Any] = {}
        if dow_raw:
            try:
                dow = int(dow_raw)
                if 0 <= dow <= 6:
                    update_fields["default_day_of_week"] = dow
            except ValueError:
                ctx.interaction.respond(
                    content="Day of week must be an integer 0-6 (0=Sunday).",
                    ephemeral=True,
                )
                return
        else:
            update_fields["default_day_of_week"] = None
        if time_raw:
            import re
            if not re.match(r"^\d{1,2}:\d{2}$", time_raw):
                ctx.interaction.respond(
                    content="Time must be `HH:MM` (24-hour).", ephemeral=True
                )
                return
            update_fields["default_time_local"] = time_raw
        else:
            update_fields["default_time_local"] = None
        st_campaigns.update_settings(ctx, campaign_id, update_fields)
    else:
        ctx.interaction.respond(content="Unknown section.", ephemeral=True)
        return

    new_settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    _show_settings_panel(ctx, campaign, new_settings)


# ── Toggle buttons & NPC visibility select ────────────────────────────────


@plugin.on_component(prefix=f"{ids.CUSTOM_ID_PREFIX}:toggle:")
def handle_settings_toggle(ctx, event):
    parsed = ids.parse_settings_toggle_btn(event.get("custom_id") or "")
    if not parsed:
        return
    toggle_key, campaign_id = parsed
    if toggle_key not in {
        "rsvp_required", "maybe_allowed", "alternate_times_allowed",
        "recap_draft_first", "quest_log_public", "ping_on_reminders",
    }:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    # Default the boolean only if the column hasn't been set yet
    default_true = toggle_key in {"maybe_allowed", "recap_draft_first", "quest_log_public"}
    current = bool(settings.get(toggle_key, default_true))
    st_campaigns.update_settings(ctx, campaign_id, {toggle_key: not current})
    refreshed = st_campaigns.get_settings(ctx, campaign_id) or {}
    ctx.interaction.respond(
        content=f"**Toggles for {campaign['name']}**",
        components=ui_components.toggles_panel_components(campaign_id, refreshed),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.CUSTOM_ID_PREFIX}:npc_vis_set:")
def handle_settings_npc_vis(ctx, event):
    campaign_id = ids.parse_settings_npc_vis_select(event.get("custom_id") or "")
    if campaign_id is None:
        return
    values = event.get("values") or []
    if not values:
        return
    chosen = str(values[0])
    if chosen not in {"public", "partial", "dm_only"}:
        ctx.interaction.respond(content="Invalid visibility.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    st_campaigns.update_settings(ctx, campaign_id, {"npc_default_visibility": chosen})
    refreshed = st_campaigns.get_settings(ctx, campaign_id) or {}
    _show_settings_panel(ctx, campaign, refreshed)


@plugin.on_component(prefix=f"{ids.CUSTOM_ID_PREFIX}:settings_back:")
def handle_settings_back(ctx, event):
    campaign_id = ids.parse_single_int_after(event.get("custom_id") or "", "settings_back")
    if campaign_id is None:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not (campaign and permissions.require_can_manage(ctx, event, campaign, settings)):
        return
    _show_settings_panel(ctx, campaign, settings)


# ── /campaign info ────────────────────────────────────────────────────────


def _campaign_info(ctx, event):
    campaign_id = get_option_int(event, "campaign_id")
    campaign = _resolve_campaign(
        ctx, event, campaign_id,
        picker_target=ids.PICKER_CAMPAIGN_FOR_INFO,
        prompt="Pick a campaign to view:",
    )
    if not campaign:
        return
    _render_campaign_info(ctx, event, int(campaign["id"]))


def _render_campaign_info(ctx, event, campaign_id: int):
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    next_session = st_sessions.next_session_for_campaign(ctx, campaign_id)
    party = st_party.list_active_party(ctx, campaign_id)
    viewer_is_dm = permissions.can_manage_campaign(event, campaign, settings)
    quests = st_quests.list_quests_for_campaign(
        ctx, campaign_id, status="active", include_dm_only=viewer_is_dm, limit=200
    )
    embed = ui_embeds.campaign_info_embed(
        campaign,
        settings,
        next_session=next_session,
        party_size=len(party),
        active_quest_count=len(quests),
    )
    ctx.interaction.respond(
        embeds=[embed],
        components=ui_components.campaign_info_components(campaign_id),
        ephemeral=True,
    )


# ── View buttons triggered from session announce embed / past-recap list ──


@plugin.on_component(prefix=f"{ids.CUSTOM_ID_PREFIX}:view_camp:")  # type: ignore[attr-defined]
def handle_view_campaign_info_button(ctx, event):
    campaign_id = ids.parse_single_int_after(event.get("custom_id") or "", "view_camp")
    if campaign_id is None:
        return
    _render_campaign_info(ctx, event, campaign_id)


@plugin.on_component(prefix=f"{ids.CUSTOM_ID_PREFIX}:view_recaps:")  # type: ignore[attr-defined]
def handle_view_campaign_recaps_button(ctx, event):
    from plugin_module.storage import recaps as st_recaps
    campaign_id = ids.parse_single_int_after(event.get("custom_id") or "", "view_recaps")
    if campaign_id is None:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    recaps = st_recaps.list_posted_for_campaign(ctx, campaign_id, limit=25)
    ctx.interaction.respond(
        embeds=[ui_embeds.recap_list_embed(campaign, recaps)],
        components=ui_components.recap_list_components(recaps),
        ephemeral=True,
    )


# ── Shared helpers ────────────────────────────────────────────────────────


def _resolve_campaign(
    ctx, event, campaign_id: Optional[int], *, picker_target: str, prompt: str
) -> Optional[Dict[str, Any]]:
    """Either return the named campaign, or send a picker and return None."""
    if campaign_id:
        campaign = st_campaigns.get_campaign(ctx, campaign_id)
        if campaign:
            return campaign
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return None

    all_campaigns = st_campaigns.list_campaigns_for_server(ctx)
    if not all_campaigns:
        ctx.interaction.respond(
            content="No campaigns yet in this server. Run `/campaign create` first.",
            ephemeral=True,
        )
        return None
    if len(all_campaigns) == 1:
        return st_campaigns.get_campaign(ctx, int(all_campaigns[0]["id"]))

    rows = ui_components.campaign_picker(picker_target, all_campaigns)
    ctx.interaction.respond(content=prompt, components=rows, ephemeral=True)
    return None


def _picked_id(event) -> Optional[int]:
    values = event.get("values") or []
    if not values:
        return None
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return None


def _parse_id(text: str) -> Optional[int]:
    if not text:
        return None
    digits = "".join(c for c in text if c.isdigit())
    if not digits:
        return None
    try:
        return int(digits)
    except (TypeError, ValueError):
        return None


def _parse_offsets(text: str) -> list:
    if not text:
        return []
    out = []
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        try:
            v = int(chunk)
            if 1 <= v <= 7 * 24 * 60:  # cap at one week
                out.append(v)
        except (TypeError, ValueError):
            continue
    return out
