"""Session recap: /session recap entry, modal, post/draft buttons, DM notes append."""
from typing import Any, Dict, Optional

from plugin_module import plugin
from plugin_module.constants import (
    CUSTOM_ID_PREFIX,
    INTERACTION_TYPE_MODAL_SUBMIT,
    MODAL_TITLE_MAX,
)
from plugin_module.core import ids, permissions, safe_discord
from plugin_module.core.option_reader import (
    get_invoking_user_id,
    get_modal_value,
    get_option_int,
)
from plugin_module.storage import campaigns as st_campaigns
from plugin_module.storage import recaps as st_recaps
from plugin_module.storage import sessions as st_sessions
from plugin_module.ui import components as ui_components
from plugin_module.ui import embeds as ui_embeds
from plugin_module.ui import modals as ui_modals


def start_recap_flow(ctx, event):
    """Called from session.handle_session when subcommand == 'recap'."""
    session_id = get_option_int(event, "session_id")
    if session_id:
        _send_recap_modal(ctx, event, session_id)
        return
    # Picker: recent sessions (completed or recently past)
    recent = ctx.sql.query(
        """
        SELECT id, session_number, title, starts_at
          FROM dnd_sessions
         WHERE discord_srv_id = %s
           AND (status = 'completed' OR (status = 'scheduled' AND starts_at < NOW()))
         ORDER BY starts_at DESC LIMIT 25
        """,
        [int(ctx.server_id)],
    )
    if not recent:
        ctx.interaction.respond(
            content="No completed sessions yet to recap.", ephemeral=True
        )
        return
    ctx.interaction.respond(
        content="Pick the session to recap:",
        components=ui_components.session_picker(
            ids.PICKER_SESSION_FOR_RECAP, recent, placeholder="Pick a session…"
        ),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_SESSION_FOR_RECAP}")
def handle_recap_picker(ctx, event):
    session_id = _picked_id(event)
    if not session_id:
        return
    _send_recap_modal(ctx, event, session_id)


@plugin.on_component(prefix=f"{CUSTOM_ID_PREFIX}:recap_create:")
def handle_recap_create_button(ctx, event):
    """Triggered by the 'Create Recap' button on the announce embed after the session ends."""
    session_id = ids.parse_single_int_after(event.get("custom_id") or "", "recap_create")
    if session_id is None:
        return
    _send_recap_modal(ctx, event, session_id)


def _send_recap_modal(ctx, event, session_id: int):
    session = st_sessions.get_session(ctx, session_id)
    if not session:
        ctx.interaction.respond(content="Session not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    default_title = f"Session {session.get('session_number') or session['id']} recap"
    ctx.interaction.send_modal(
        title=f"Recap — #{session.get('session_number') or session['id']}"[:MODAL_TITLE_MAX],
        custom_id=ids.recap_modal_id(session_id),
        fields=ui_modals.recap_fields(default_title=default_title),
    )


@plugin.on_event("interaction_create")
def handle_recap_modal_submit(ctx, event):
    if event.get("interaction_type") != INTERACTION_TYPE_MODAL_SUBMIT:
        return
    session_id = ids.parse_recap_modal_id(event.get("custom_id") or "")
    if session_id is None:
        return
    _apply_recap_modal(ctx, event, session_id)


def _apply_recap_modal(ctx, event, session_id: int):
    session = st_sessions.get_session(ctx, session_id)
    if not session:
        ctx.interaction.respond(content="Session not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return

    title = get_modal_value(event, "title")
    summary = get_modal_value(event, "summary")
    if not summary:
        ctx.interaction.respond(content="Summary is required.", ephemeral=True)
        return
    highlights = get_modal_value(event, "highlights")
    loot = get_modal_value(event, "loot")
    cliffhanger = get_modal_value(event, "cliffhanger")

    recap = st_recaps.create_draft(
        ctx,
        session_id=session_id,
        campaign_id=int(session["campaign_id"]),
        title=title,
        summary=summary,
        highlights=highlights,
        loot=loot,
        cliffhanger=cliffhanger,
        author_user_id=get_invoking_user_id(event),
    )
    if not recap:
        ctx.interaction.respond(content="Failed to save the recap.", ephemeral=True)
        return

    # If config says instant-post, post immediately and skip the preview UX
    if not settings.get("recap_draft_first", True):
        if _post_recap(ctx, recap, session, campaign, settings):
            ctx.interaction.respond(
                content=f"Recap posted to <#{settings.get('recap_channel_id') or settings.get('announce_channel_id')}>.",
                ephemeral=True,
            )
            return

    ctx.interaction.respond(
        embeds=[ui_embeds.recap_preview_embed(recap, session, campaign or {})],
        components=ui_components.recap_preview_buttons(int(recap["id"])),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{CUSTOM_ID_PREFIX}:recap_post:")
def handle_recap_post(ctx, event):
    recap_id = ids.parse_single_int_after(event.get("custom_id") or "", "recap_post")
    if recap_id is None:
        return
    recap = st_recaps.get_recap(ctx, recap_id)
    if not recap:
        ctx.interaction.respond(content="Recap not found.", ephemeral=True)
        return
    session = st_sessions.get_session(ctx, int(recap["session_id"]))
    campaign = st_campaigns.get_campaign(ctx, int(recap["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(recap["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    if recap.get("status") == "posted":
        ctx.interaction.respond(content="Already posted.", ephemeral=True)
        return
    if _post_recap(ctx, recap, session or {}, campaign or {}, settings):
        ctx.interaction.respond(
            embeds=[ui_embeds.success_embed("Recap posted.")], ephemeral=True
        )
    else:
        ctx.interaction.respond(
            content="Couldn't post the recap — is a recap or announce channel configured?",
            ephemeral=True,
        )


def _post_recap(
    ctx,
    recap: Dict[str, Any],
    session: Dict[str, Any],
    campaign: Dict[str, Any],
    settings: Dict[str, Any],
) -> bool:
    channel_id = settings.get("recap_channel_id") or settings.get("announce_channel_id")
    if not channel_id:
        return False
    embed = ui_embeds.recap_posted_embed(recap, session, campaign)
    msg_id = safe_discord.safe_send_message(
        ctx,
        channel_id=str(channel_id),
        action="post the recap",
        on_error_respond=False,
        embeds=[embed],
    )
    if not msg_id:
        return False
    st_recaps.mark_posted(
        ctx, int(recap["id"]), channel_id=int(channel_id), message_id=int(msg_id)
    )
    return True


@plugin.on_component(prefix=f"{CUSTOM_ID_PREFIX}:recap_keep:")
def handle_recap_keep(ctx, event):
    ctx.interaction.respond(
        content="Saved as draft — pick it back up later with `/session recap`.",
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{CUSTOM_ID_PREFIX}:recap_view:")
def handle_recap_view(ctx, event):
    """Render a posted recap ephemerally to the clicker."""
    recap_id = ids.parse_single_int_after(event.get("custom_id") or "", "recap_view")
    if recap_id is None:
        return
    recap = st_recaps.get_recap(ctx, recap_id)
    if not recap or recap.get("status") != "posted":
        ctx.interaction.respond(content="That recap is no longer available.", ephemeral=True)
        return
    session = st_sessions.get_session(ctx, int(recap["session_id"]))
    campaign = st_campaigns.get_campaign(ctx, int(recap["campaign_id"]))
    if not (session and campaign):
        ctx.interaction.respond(content="Recap data missing.", ephemeral=True)
        return
    ctx.interaction.respond(
        embeds=[ui_embeds.recap_posted_embed(recap, session, campaign)],
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{CUSTOM_ID_PREFIX}:recap_dmnotes:")
def handle_recap_dmnotes_button(ctx, event):
    recap_id = ids.parse_single_int_after(event.get("custom_id") or "", "recap_dmnotes")
    if recap_id is None:
        return
    recap = st_recaps.get_recap(ctx, recap_id)
    if not recap:
        ctx.interaction.respond(content="Recap not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(recap["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(recap["campaign_id"])) or {}
    if not permissions.require_can_view_dm_notes(ctx, event, campaign, settings):
        return
    ctx.interaction.send_modal(
        title="DM notes (private)"[:MODAL_TITLE_MAX],
        custom_id=ids.recap_dmnotes_modal_id(recap_id),
        fields=ui_modals.recap_dmnotes_fields(),
    )


@plugin.on_event("interaction_create")
def handle_recap_dmnotes_modal(ctx, event):
    if event.get("interaction_type") != INTERACTION_TYPE_MODAL_SUBMIT:
        return
    custom_id = event.get("custom_id") or ""
    if not custom_id.startswith(f"{CUSTOM_ID_PREFIX}:recap_dmnotes_modal:"):
        return
    parts = custom_id.split(":")
    if len(parts) != 3:
        return
    try:
        recap_id = int(parts[2])
    except (TypeError, ValueError):
        return
    recap = st_recaps.get_recap(ctx, recap_id)
    if not recap:
        ctx.interaction.respond(content="Recap not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(recap["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(recap["campaign_id"])) or {}
    if not permissions.require_can_view_dm_notes(ctx, event, campaign, settings):
        return
    notes = get_modal_value(event, "dm_notes")
    st_recaps.set_dm_notes(ctx, recap_id, notes)
    ctx.interaction.respond(
        content="DM notes saved (private — never shown to players).",
        ephemeral=True,
    )


def _picked_id(event) -> Optional[int]:
    values = event.get("values") or []
    if not values:
        return None
    try:
        return int(values[0])
    except (TypeError, ValueError):
        return None
