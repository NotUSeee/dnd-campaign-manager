"""/session schedule | list | cancel | attendance + cancel-confirm + recurrence picker."""
from datetime import timedelta
from typing import Any, Dict, Optional

from plugin_module import plugin
from plugin_module.constants import (
    CUSTOM_ID_PREFIX,
    DEFAULT_SESSION_DURATION_MINUTES,
    INTERACTION_TYPE_MODAL_SUBMIT,
    MODAL_TITLE_MAX,
    SERIES_MATERIALIZE_AHEAD,
)
from plugin_module.core import ids, permissions
from plugin_module.core import safe_discord
from plugin_module.core.option_reader import (
    get_invoking_user_id,
    get_modal_value,
    get_option_int,
    get_option_str,
    get_subcommand,
)
from plugin_module.core.time_util import (
    advance_recurrence,
    compute_next_reminder_due_at,
    next_date_matching_weekday,
    parse_date_time_local,
)
from plugin_module.storage import attendance as st_attendance
from plugin_module.storage import campaigns as st_campaigns
from plugin_module.storage import rsvps as st_rsvps
from plugin_module.storage import sessions as st_sessions
from plugin_module.ui import components as ui_components
from plugin_module.ui import embeds as ui_embeds
from plugin_module.ui import modals as ui_modals


@plugin.on_slash_command("session")
def handle_session(ctx, event):
    sub = get_subcommand(event)
    if sub == "schedule":
        return _session_schedule(ctx, event)
    if sub == "list":
        return _session_list(ctx, event)
    if sub == "cancel":
        return _session_cancel(ctx, event)
    if sub == "attendance":
        return _session_attendance(ctx, event)
    if sub == "recap":
        from plugin_module.handlers import recap as recap_handler
        return recap_handler.start_recap_flow(ctx, event)
    ctx.interaction.respond(content="Unknown subcommand.", ephemeral=True)


# ── /session schedule ────────────────────────────────────────────────────


def _session_schedule(ctx, event):
    campaign_id = get_option_int(event, "campaign_id")
    campaign = _resolve_campaign(
        ctx, event, campaign_id,
        picker_target=ids.PICKER_CAMPAIGN_FOR_SESSION_SCHEDULE,
        prompt="Pick the campaign to schedule a session for:",
    )
    if not campaign:
        return
    _send_schedule_modal(ctx, event, campaign)


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_CAMPAIGN_FOR_SESSION_SCHEDULE}")
def handle_schedule_picker(ctx, event):
    campaign_id = _picked_id(event)
    if not campaign_id:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    _send_schedule_modal(ctx, event, campaign)


def _send_schedule_modal(ctx, event, campaign: Dict[str, Any]):
    settings = st_campaigns.get_settings(ctx, int(campaign["id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    if not settings.get("announce_channel_id"):
        ctx.interaction.respond(
            content=(
                "This campaign has no announcement channel configured. "
                "Run `/campaign settings` first."
            ),
            ephemeral=True,
        )
        return
    tz = str(campaign.get("timezone") or "UTC")
    default_dow = settings.get("default_day_of_week")
    default_date = next_date_matching_weekday(default_dow, tz) if default_dow is not None else ""
    default_time = str(settings.get("default_time_local") or "")
    ctx.interaction.send_modal(
        title=f"Schedule — {campaign['name']}"[:MODAL_TITLE_MAX],
        custom_id=ids.modal_session_schedule_id(int(campaign["id"])),
        fields=ui_modals.session_schedule_fields(
            campaign_tz=tz,
            default_date=default_date or "",
            default_time_local=default_time,
        ),
    )


@plugin.on_event("interaction_create")
def handle_schedule_modal_submit(ctx, event):
    if event.get("interaction_type") != INTERACTION_TYPE_MODAL_SUBMIT:
        return
    campaign_id = ids.parse_modal_session_schedule(event.get("custom_id") or "")
    if campaign_id is None:
        return
    _apply_schedule_modal(ctx, event, campaign_id)


def _apply_schedule_modal(ctx, event, campaign_id: int):
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    settings = st_campaigns.get_settings(ctx, campaign_id) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return

    date_str = get_modal_value(event, "date")
    time_str = get_modal_value(event, "time_local")
    duration_str = get_modal_value(event, "duration_min") or str(DEFAULT_SESSION_DURATION_MINUTES)
    title = get_modal_value(event, "title")
    notes = get_modal_value(event, "notes_for_players")

    starts_at = parse_date_time_local(date_str, time_str, str(campaign.get("timezone") or "UTC"))
    if not starts_at:
        ctx.interaction.respond(
            content=(
                "Couldn't parse the date or time. Use `YYYY-MM-DD` and 24-hour `HH:MM` "
                "(e.g. `2026-06-15` and `19:00`)."
            ),
            ephemeral=True,
        )
        return

    try:
        duration = max(15, min(12 * 60, int(duration_str)))
    except (TypeError, ValueError):
        duration = DEFAULT_SESSION_DURATION_MINUTES

    offsets = settings.get("reminder_offsets_minutes") or []
    next_due = compute_next_reminder_due_at(starts_at, list(offsets), [])

    session = st_sessions.create_session(
        ctx,
        campaign_id=campaign_id,
        title=title,
        notes_for_players=notes,
        starts_at=starts_at,
        duration_minutes=duration,
        created_by_user_id=get_invoking_user_id(event),
        announce_channel_id=settings.get("announce_channel_id"),
        next_reminder_due_at=next_due,
    )
    if not session:
        ctx.interaction.respond(content="Failed to create the session.", ephemeral=True)
        return

    _post_announce(ctx, campaign, settings, session)
    ctx.interaction.respond(
        content=(
            f"Session scheduled. Announcement posted in "
            f"<#{settings['announce_channel_id']}>. Make it recurring?"
        ),
        components=ui_components.recurrence_picker(int(session["id"])),
        ephemeral=True,
    )


def _post_announce(
    ctx, campaign: Dict[str, Any], settings: Dict[str, Any], session: Dict[str, Any]
) -> None:
    embed = ui_embeds.session_announce_embed(
        campaign=campaign,
        session=session,
        rsvp_counts={"attending": 0, "maybe": 0, "unavailable": 0},
        attendee_user_ids=[],
        maybe_user_ids=[],
        unavailable_user_ids=[],
        rsvp_required=bool(settings.get("rsvp_required", False)),
    )
    components = ui_components.session_announce_components(
        session,
        maybe_allowed=bool(settings.get("maybe_allowed", True)),
        alternate_times_allowed=bool(settings.get("alternate_times_allowed", False)),
        campaign_id=int(campaign["id"]),
    )
    message_id = safe_discord.safe_send_message(
        ctx,
        channel_id=str(settings["announce_channel_id"]),
        action="post the session announcement",
        embeds=[embed],
        components=components,
    )
    if message_id:
        st_sessions.update_announce_message(
            ctx, int(session["id"]),
            channel_id=int(settings["announce_channel_id"]),
            message_id=int(message_id),
        )


# ── Recurrence picker (after schedule modal) ─────────────────────────────


@plugin.on_component(prefix=f"{CUSTOM_ID_PREFIX}:recurrence:")
def handle_recurrence_picker(ctx, event):
    session_id = ids.parse_recurrence_picker(event.get("custom_id") or "")
    if session_id is None:
        return
    values = event.get("values") or []
    if not values:
        return
    choice = str(values[0])

    if choice == "none":
        ctx.interaction.respond(content="Single session, no recurrence.", ephemeral=True)
        return

    session = st_sessions.get_session(ctx, session_id)
    if not session:
        ctx.interaction.respond(content="Session not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return

    starts_at = session["starts_at"]
    time_local = starts_at.strftime("%H:%M") if starts_at else None
    weekday = _weekday_short(starts_at)
    rule: Dict[str, Any] = {"time_local": time_local} if time_local else {}

    if choice == "weekly":
        rule.update({"freq": "WEEKLY", "interval": 1, "byweekday": weekday})
    elif choice == "biweekly":
        rule.update({"freq": "BIWEEKLY", "interval": 2, "byweekday": weekday})
    elif choice == "monthly":
        rule.update({"freq": "MONTHLY_BY_DAY", "interval": 1})
    else:
        ctx.interaction.respond(content="Unknown recurrence choice.", ephemeral=True)
        return

    st_sessions.set_recurrence_rule(ctx, session_id, rule)

    # Materialize the next instances upfront
    offsets = settings.get("reminder_offsets_minutes") or []
    tz_name = str(campaign.get("timezone") or "UTC") if campaign else "UTC"
    next_start = starts_at
    materialized = 0
    for _ in range(max(0, SERIES_MATERIALIZE_AHEAD - 1)):
        next_start = advance_recurrence(next_start, rule, tz_name=tz_name)
        if not next_start:
            break
        next_due = compute_next_reminder_due_at(next_start, list(offsets), [])
        new_sess = st_sessions.create_session(
            ctx,
            campaign_id=int(session["campaign_id"]),
            title=session.get("title") or "",
            notes_for_players=session.get("notes_for_players") or "",
            starts_at=next_start,
            duration_minutes=int(session.get("duration_minutes") or DEFAULT_SESSION_DURATION_MINUTES),
            created_by_user_id=get_invoking_user_id(event) or str(session.get("created_by_user_id")),
            announce_channel_id=session.get("announce_channel_id") or settings.get("announce_channel_id"),
            series_id=int(session["id"]),
            recurrence_rule=None,
            next_reminder_due_at=next_due,
        )
        if not new_sess:
            break
        if settings.get("announce_channel_id") and campaign:
            _post_announce(ctx, campaign, settings, new_sess)
        materialized += 1

    ctx.interaction.respond(
        content=(
            f"Recurrence set ({choice}); materialized **{materialized}** more upcoming session(s)."
        ),
        ephemeral=True,
    )


# ── /session list ────────────────────────────────────────────────────────


def _session_list(ctx, event):
    campaign_id = get_option_int(event, "campaign_id")
    scope = get_option_str(event, "scope") or "upcoming"
    campaign = _resolve_campaign(
        ctx, event, campaign_id,
        picker_target=ids.PICKER_CAMPAIGN_FOR_SESSION_LIST,
        prompt="Pick a campaign to list sessions for:",
    )
    if not campaign:
        return
    sessions = st_sessions.list_sessions_for_campaign(ctx, int(campaign["id"]), scope=scope)
    ctx.interaction.respond(
        embeds=[ui_embeds.session_list_embed(campaign, sessions, scope=scope)],
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_CAMPAIGN_FOR_SESSION_LIST}")
def handle_session_list_picker(ctx, event):
    campaign_id = _picked_id(event)
    if not campaign_id:
        return
    campaign = st_campaigns.get_campaign(ctx, campaign_id)
    if not campaign:
        ctx.interaction.respond(content="Campaign not found.", ephemeral=True)
        return
    sessions = st_sessions.list_sessions_for_campaign(ctx, campaign_id, scope="upcoming")
    ctx.interaction.respond(
        embeds=[ui_embeds.session_list_embed(campaign, sessions, scope="upcoming")],
        ephemeral=True,
    )


# ── /session cancel ──────────────────────────────────────────────────────


def _session_cancel(ctx, event):
    session_id = get_option_int(event, "session_id")
    if session_id:
        _cancel_confirm_for(ctx, event, session_id)
        return

    # Picker fallback — show upcoming scheduled sessions from any campaign
    upcoming = ctx.sql.query(
        """
        SELECT id, session_number, title, starts_at
          FROM dnd_sessions
         WHERE discord_srv_id = %s AND status = 'scheduled' AND starts_at >= NOW()
         ORDER BY starts_at LIMIT 25
        """,
        [int(ctx.server_id)],
    )
    if not upcoming:
        ctx.interaction.respond(content="No upcoming sessions to cancel.", ephemeral=True)
        return
    ctx.interaction.respond(
        content="Pick the session to cancel:",
        components=ui_components.session_picker(
            ids.PICKER_SESSION_FOR_CANCEL, upcoming, placeholder="Pick a session…"
        ),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_SESSION_FOR_CANCEL}")
def handle_cancel_picker(ctx, event):
    session_id = _picked_id(event)
    if not session_id:
        return
    _cancel_confirm_for(ctx, event, session_id)


def _cancel_confirm_for(ctx, event, session_id: int):
    session = st_sessions.get_session(ctx, session_id)
    if not session or session.get("status") != "scheduled":
        ctx.interaction.respond(
            content="That session isn't scheduled — nothing to cancel.", ephemeral=True
        )
        return
    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    ctx.interaction.respond(
        embeds=[ui_embeds.session_cancel_confirm_embed(session)],
        components=ui_components.cancel_confirm_buttons(session_id),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{CUSTOM_ID_PREFIX}:cancel_confirm:")
def handle_cancel_confirm(ctx, event):
    session_id = ids.parse_single_int_after(event.get("custom_id") or "", "cancel_confirm")
    if session_id is None:
        return
    session = st_sessions.get_session(ctx, session_id)
    if not session:
        ctx.interaction.respond(content="Session not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    affected = st_sessions.cancel_session(ctx, session_id)
    if not affected:
        ctx.interaction.respond(content="Session was already cancelled.", ephemeral=True)
        return

    # Edit the announcement to show cancellation
    if session.get("announce_channel_id") and session.get("announce_message_id"):
        refreshed = st_sessions.get_session(ctx, session_id)
        counts = st_rsvps.counts_by_status(ctx, session_id)
        attendees = st_rsvps.list_user_ids_by_status(ctx, session_id, "attending")
        maybes = st_rsvps.list_user_ids_by_status(ctx, session_id, "maybe")
        unavail = st_rsvps.list_user_ids_by_status(ctx, session_id, "unavailable")
        safe_discord.safe_edit_message(
            ctx,
            channel_id=str(session["announce_channel_id"]),
            message_id=str(session["announce_message_id"]),
            embeds=[
                ui_embeds.session_announce_embed(
                    campaign=campaign or {},
                    session=refreshed,
                    rsvp_counts=counts,
                    attendee_user_ids=attendees,
                    maybe_user_ids=maybes,
                    unavailable_user_ids=unavail,
                    rsvp_required=bool(settings.get("rsvp_required", False)),
                )
            ],
            components=[],
        )

    ctx.interaction.respond(
        embeds=[ui_embeds.success_embed("Session cancelled.")],
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{CUSTOM_ID_PREFIX}:cancel_keep:")
def handle_cancel_keep(ctx, event):
    ctx.interaction.respond(content="Kept as scheduled.", ephemeral=True)


# ── "Propose alternate time" button on the session announce embed ─────────


@plugin.on_component(prefix=f"{CUSTOM_ID_PREFIX}:alt_time:")
def handle_alt_time_button(ctx, event):
    session_id = ids.parse_single_int_after(event.get("custom_id") or "", "alt_time")
    if session_id is None:
        return
    session = st_sessions.get_session(ctx, session_id)
    if not session or session.get("status") != "scheduled":
        ctx.interaction.respond(
            content="That session is no longer open for proposals.", ephemeral=True
        )
        return
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}
    if not settings.get("alternate_times_allowed"):
        ctx.interaction.respond(
            content="This campaign isn't accepting alternate-time proposals.",
            ephemeral=True,
        )
        return
    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    tz = str((campaign or {}).get("timezone") or "UTC")
    ctx.interaction.send_modal(
        title="Propose alternate time"[:MODAL_TITLE_MAX],
        custom_id=ids.suggest_alt_time_modal_id(session_id),
        fields=ui_modals.alt_time_fields(campaign_tz=tz),
    )


@plugin.on_event("interaction_create")
def handle_alt_time_modal(ctx, event):
    if event.get("interaction_type") != INTERACTION_TYPE_MODAL_SUBMIT:
        return
    session_id = ids.parse_modal_alt_time(event.get("custom_id") or "")
    if session_id is None:
        return
    session = st_sessions.get_session(ctx, session_id)
    if not session or session.get("status") != "scheduled":
        ctx.interaction.respond(
            content="That session is no longer open for proposals.", ephemeral=True
        )
        return
    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}
    if not settings.get("alternate_times_allowed"):
        ctx.interaction.respond(
            content="This campaign isn't accepting alternate-time proposals.",
            ephemeral=True,
        )
        return

    date_str = get_modal_value(event, "date")
    time_str = get_modal_value(event, "time_local")
    reason = get_modal_value(event, "reason")
    tz = str((campaign or {}).get("timezone") or "UTC")
    proposed_at = parse_date_time_local(date_str, time_str, tz)
    if not proposed_at:
        ctx.interaction.respond(
            content="Couldn't parse that date/time. Use `YYYY-MM-DD` and `HH:MM` (24-hour).",
            ephemeral=True,
        )
        return

    embed = ui_embeds.alt_time_proposal_embed(
        session=session,
        campaign=campaign or {},
        proposer_user_id=get_invoking_user_id(event),
        proposed_at=proposed_at,
        reason=reason,
    )
    channel_id = session.get("announce_channel_id") or settings.get("announce_channel_id")
    posted = False
    if channel_id:
        mid = safe_discord.safe_send_message(
            ctx,
            channel_id=str(channel_id),
            action="post the alternate-time proposal",
            on_error_respond=False,
            embeds=[embed],
        )
        posted = bool(mid)
    if posted:
        ctx.interaction.respond(
            content="Sent — your alternate time was posted for the group to see.",
            ephemeral=True,
        )
    else:
        ctx.interaction.respond(
            embeds=[embed],
            content="(Couldn't post publicly. Share this with your DM directly.)",
            ephemeral=True,
        )


# ── /session attendance ──────────────────────────────────────────────────


def _session_attendance(ctx, event):
    session_id = get_option_int(event, "session_id")
    if session_id:
        _attendance_for(ctx, event, session_id)
        return

    recent = ctx.sql.query(
        """
        SELECT id, session_number, title, starts_at
          FROM dnd_sessions
         WHERE discord_srv_id = %s
           AND (status = 'completed'
                OR (status = 'scheduled' AND starts_at < NOW())
                OR (status = 'scheduled' AND starts_at < NOW() + INTERVAL '2 hours'))
         ORDER BY starts_at DESC LIMIT 25
        """,
        [int(ctx.server_id)],
    )
    if not recent:
        ctx.interaction.respond(
            content="No recent or upcoming sessions to record attendance for.",
            ephemeral=True,
        )
        return
    ctx.interaction.respond(
        content="Pick the session to record attendance for:",
        components=ui_components.session_picker(
            ids.PICKER_SESSION_FOR_ATTENDANCE, recent, placeholder="Pick a session…"
        ),
        ephemeral=True,
    )


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}{ids.PICKER_SESSION_FOR_ATTENDANCE}")
def handle_attendance_picker(ctx, event):
    session_id = _picked_id(event)
    if not session_id:
        return
    _attendance_for(ctx, event, session_id)


def _attendance_for(ctx, event, session_id: int):
    session = st_sessions.get_session(ctx, session_id)
    if not session:
        ctx.interaction.respond(content="Session not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return
    rsvped = st_rsvps.list_user_ids_by_status(ctx, session_id, "attending") + \
             st_rsvps.list_user_ids_by_status(ctx, session_id, "maybe")
    embed = ui_embeds.attendance_prompt_embed(session, campaign or {}, rsvped)
    components = ui_components.attendance_select(session_id, rsvped)
    ctx.interaction.respond(embeds=[embed], components=components, ephemeral=True)


@plugin.on_component(prefix=f"{ids.PICKER_PREFIX}attendance:")
def handle_attendance_select(ctx, event):
    custom_id = event.get("custom_id") or ""
    try:
        session_id = int(custom_id.split(":")[-1])
    except (ValueError, IndexError):
        return
    session = st_sessions.get_session(ctx, session_id)
    if not session:
        ctx.interaction.respond(content="Session not found.", ephemeral=True)
        return
    campaign = st_campaigns.get_campaign(ctx, int(session["campaign_id"]))
    settings = st_campaigns.get_settings(ctx, int(session["campaign_id"])) or {}
    if not permissions.require_can_manage(ctx, event, campaign, settings):
        return

    chosen = {str(v) for v in (event.get("values") or [])}
    rsvped = set(str(u) for u in (
        st_rsvps.list_user_ids_by_status(ctx, session_id, "attending")
        + st_rsvps.list_user_ids_by_status(ctx, session_id, "maybe")
    ))

    present = sorted(int(uid) for uid in chosen if uid in rsvped)
    absent = sorted(int(uid) for uid in rsvped if uid not in chosen)

    for uid in present:
        st_attendance.log_attendance(ctx, session_id=session_id, user_id=str(uid), attended=True)
    for uid in absent:
        st_attendance.log_attendance(ctx, session_id=session_id, user_id=str(uid), attended=False)

    st_sessions.mark_completed(ctx, session_id)
    ctx.interaction.respond(
        embeds=[ui_embeds.attendance_recorded_embed(session, present, absent)],
        ephemeral=True,
    )


# ── Shared helpers ────────────────────────────────────────────────────────


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


def _weekday_short(dt) -> Optional[str]:
    if not dt:
        return None
    days = ["MO", "TU", "WE", "TH", "FR", "SA", "SU"]
    return days[dt.weekday()]
