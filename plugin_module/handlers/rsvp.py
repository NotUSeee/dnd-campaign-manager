"""RSVP button handlers — Attending / Maybe / Unavailable."""
from plugin_module import plugin
from plugin_module.core import ids, safe_discord
from plugin_module.core.option_reader import get_invoking_user_id
from plugin_module.storage import campaigns as st_campaigns
from plugin_module.storage import rsvps as st_rsvps
from plugin_module.storage import sessions as st_sessions
from plugin_module.ui import components as ui_components
from plugin_module.ui import embeds as ui_embeds


@plugin.on_component(prefix=ids.RSVP_PREFIX)
def handle_rsvp(ctx, event):
    parsed = ids.parse_rsvp_id(event.get("custom_id") or "")
    if not parsed:
        return
    session_id, status = parsed
    if status not in st_rsvps.VALID_STATUSES:
        ctx.interaction.respond(content="Unknown RSVP status.", ephemeral=True)
        return

    session = st_sessions.get_session(ctx, session_id)
    if not session:
        ctx.interaction.respond(
            content="That session is no longer available.",
            ephemeral=True,
        )
        return
    if session.get("status") != "scheduled":
        ctx.interaction.respond(
            content="RSVPs are closed for this session.",
            ephemeral=True,
        )
        return

    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}

    if status == "maybe" and not settings.get("maybe_allowed", True):
        ctx.interaction.respond(
            content="This campaign doesn't allow 'maybe' RSVPs.",
            ephemeral=True,
        )
        return

    ctx.interaction.defer(ephemeral=True)

    user_id = get_invoking_user_id(event)
    if not user_id:
        ctx.interaction.followup(content="Couldn't identify your user.", ephemeral=True)
        return

    st_rsvps.upsert_rsvp(ctx, session_id=session_id, user_id=user_id, status=status)

    # Refresh embed with new counts
    counts = st_rsvps.counts_by_status(ctx, session_id)
    attendees = st_rsvps.list_user_ids_by_status(ctx, session_id, "attending")
    maybes = st_rsvps.list_user_ids_by_status(ctx, session_id, "maybe")
    unavail = st_rsvps.list_user_ids_by_status(ctx, session_id, "unavailable")

    embed = ui_embeds.session_announce_embed(
        campaign=campaign or {},
        session=session,
        rsvp_counts=counts,
        attendee_user_ids=attendees,
        maybe_user_ids=maybes,
        unavailable_user_ids=unavail,
        rsvp_required=bool(settings.get("rsvp_required", False)),
    )
    components = ui_components.session_announce_components(
        session,
        maybe_allowed=bool(settings.get("maybe_allowed", True)),
        alternate_times_allowed=bool(settings.get("alternate_times_allowed", False)),
        campaign_id=int(session["campaign_id"]),
    )
    if session.get("announce_channel_id") and session.get("announce_message_id"):
        safe_discord.safe_edit_message(
            ctx,
            channel_id=str(session["announce_channel_id"]),
            message_id=str(session["announce_message_id"]),
            embeds=[embed],
            components=components,
        )

    confirmation = {
        "attending": "You're marked as **attending**.",
        "maybe": "You're marked as **maybe** — we'll see you if we see you.",
        "unavailable": "You're marked as **unavailable**.",
    }.get(status, "RSVP recorded.")
    ctx.interaction.followup(content=confirmation, ephemeral=True)
