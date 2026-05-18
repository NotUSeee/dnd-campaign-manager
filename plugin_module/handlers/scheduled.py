"""Reminder dispatcher (60s poll) + recurring-series auto-extension.

The dispatcher uses an atomic SQL UPDATE that conditionally appends the
offset to `reminder_offsets_sent`, providing at-most-once semantics even
under retries or concurrent ticks.
"""
from datetime import datetime, timezone
from typing import Any, Dict

from plugin_module import plugin
from plugin_module.constants import (
    REMINDER_POLL_INTERVAL_SECONDS,
    SERIES_EXTEND_THRESHOLD,
    SERIES_EXTEND_TICK_KEY,
    SERIES_EXTEND_TICK_MIN_INTERVAL_SECONDS,
    SERIES_MATERIALIZE_AHEAD,
)
from plugin_module.core.time_util import (
    advance_recurrence,
    compute_next_reminder_due_at,
    is_reminder_offset_relevant,
    now_utc,
)
from plugin_module.storage import campaigns as st_campaigns
from plugin_module.storage import reminders as st_reminders
from plugin_module.storage import sessions as st_sessions
from plugin_module.ui import embeds as ui_embeds


@plugin.schedule(REMINDER_POLL_INTERVAL_SECONDS)
def dispatch_reminders(ctx):
    try:
        _tick(ctx)
    except Exception as exc:  # noqa: BLE001
        ctx.log(f"dispatch_reminders error: {exc}", level="error", tags=["reminders"])


def _tick(ctx) -> None:
    now = now_utc()
    due = st_sessions.find_due_reminders(ctx, now, limit=50)
    if due:
        for sess in due:
            _send_for_session(ctx, sess, now)
    _maybe_extend_series(ctx, now)


def _send_for_session(ctx, sess: Dict[str, Any], now: datetime) -> None:
    settings = st_reminders.get_settings_for_session(ctx, int(sess["id"]))
    if not settings:
        # No settings row — clear due so we don't keep polling
        st_sessions.set_next_reminder_due_at(ctx, int(sess["id"]), None)
        return

    offsets = [int(o) for o in (settings.get("reminder_offsets_minutes") or [])]
    already_sent = set(int(x) for x in (sess.get("reminder_offsets_sent") or []))
    starts_at = sess["starts_at"]

    to_consider = [o for o in offsets if o > 0 and o not in already_sent]

    for offset in to_consider:
        if not is_reminder_offset_relevant(offset, starts_at, now):
            # Mark stale offsets as sent so we don't keep evaluating them
            st_sessions.mark_offset_sent_atomic(ctx, int(sess["id"]), offset)
            continue
        # Only proceed if the offset is past-due (would-have-fired already)
        from datetime import timedelta
        fire_time = starts_at - timedelta(minutes=offset)
        if fire_time > now:
            continue
        if not st_sessions.mark_offset_sent_atomic(ctx, int(sess["id"]), offset):
            continue  # raced — another worker sent it
        try:
            _post_reminder(ctx, sess, settings, offset)
        except Exception as exc:  # noqa: BLE001 — at-most-once: do not retry
            ctx.log(
                f"reminder post failed for session {sess['id']} offset {offset}: {exc}",
                level="error",
                tags=["reminders", "post_failed"],
            )

    # Recompute next due
    refreshed = st_sessions.get_session(ctx, int(sess["id"]))
    if not refreshed:
        return
    next_due = compute_next_reminder_due_at(
        refreshed["starts_at"], offsets, refreshed.get("reminder_offsets_sent") or []
    )
    st_sessions.set_next_reminder_due_at(ctx, int(sess["id"]), next_due)


def _post_reminder(ctx, sess: Dict[str, Any], settings: Dict[str, Any], offset_min: int) -> None:
    channel_id = settings.get("reminder_channel_id") or settings.get("announce_channel_id")
    if not channel_id:
        return
    campaign = {
        "id": settings.get("campaign_id"),
        "name": settings.get("campaign_name") or "Campaign",
        "timezone": settings.get("timezone") or "UTC",
    }

    # When rsvp_required is set, include the list of party members who haven't
    # responded yet so the DM and group can chase them down. Capped at 50.
    pending: list = []
    if settings.get("rsvp_required"):
        try:
            pending = st_reminders.party_user_ids_without_rsvp(
                ctx, int(sess["id"]), int(settings.get("campaign_id") or 0)
            )
        except Exception:  # noqa: BLE001 — never let this break the reminder
            pending = []

    embed = ui_embeds.session_reminder_embed(
        campaign=campaign, session=sess, offset_minutes=offset_min,
        pending_rsvp_user_ids=pending or None,
    )

    # Guardrail: ping the player role only if the DM explicitly opted in.
    # When ping_on_reminders is False we simply omit the role mention from
    # the content — Discord doesn't ping what isn't there.
    content = ""
    if settings.get("ping_on_reminders") and settings.get("player_role_id"):
        content = f"<@&{settings['player_role_id']}>"

    ctx.discord.send_message(
        channel_id=str(channel_id),
        content=content,
        embeds=[embed],
    )


def _maybe_extend_series(ctx, now: datetime) -> None:
    last_tick = ctx.kv.get(SERIES_EXTEND_TICK_KEY)
    if last_tick is not None:
        try:
            last = float(last_tick)
            if now.timestamp() - last < SERIES_EXTEND_TICK_MIN_INTERVAL_SECONDS:
                return
        except (TypeError, ValueError):
            pass

    series_ids = st_sessions.series_needing_extension(ctx, threshold=SERIES_EXTEND_THRESHOLD)
    for series_id in series_ids:
        try:
            _extend_series(ctx, series_id)
        except Exception as exc:  # noqa: BLE001
            ctx.log(
                f"series extension failed for series {series_id}: {exc}",
                level="error",
                tags=["reminders", "series"],
            )
    ctx.kv.set(SERIES_EXTEND_TICK_KEY, now.timestamp())


def _extend_series(ctx, series_id: int) -> None:
    anchor = st_sessions.latest_in_series(ctx, series_id)
    if not anchor:
        return
    rule = anchor.get("recurrence_rule")
    if not rule:
        # Series anchor changed? Look up the original anchor
        original = st_sessions.get_session(ctx, series_id)
        rule = original.get("recurrence_rule") if original else None
    if not rule:
        return

    campaign = st_campaigns.get_campaign(ctx, int(anchor["campaign_id"]))
    tz_name = (campaign.get("timezone") if campaign else None) or "UTC"
    settings = st_campaigns.get_settings(ctx, int(anchor["campaign_id"])) or {}
    offsets = [int(o) for o in (settings.get("reminder_offsets_minutes") or [])]

    current_count = st_sessions.series_session_count_future(ctx, series_id)
    to_create = max(0, SERIES_MATERIALIZE_AHEAD - current_count)
    if to_create <= 0:
        return

    next_start = anchor["starts_at"]
    if next_start.tzinfo is None:
        next_start = next_start.replace(tzinfo=timezone.utc)

    for _ in range(to_create):
        next_start = advance_recurrence(next_start, rule, tz_name=tz_name)
        if not next_start:
            return
        next_due = compute_next_reminder_due_at(next_start, offsets, [])
        st_sessions.create_session(
            ctx,
            campaign_id=int(anchor["campaign_id"]),
            title=anchor.get("title") or "",
            notes_for_players=anchor.get("notes_for_players") or "",
            starts_at=next_start,
            duration_minutes=int(anchor.get("duration_minutes") or 240),
            created_by_user_id=str(anchor.get("created_by_user_id") or 0),
            announce_channel_id=anchor.get("announce_channel_id"),
            series_id=int(series_id),
            recurrence_rule=None,  # only the anchor carries the rule
            next_reminder_due_at=next_due,
        )
