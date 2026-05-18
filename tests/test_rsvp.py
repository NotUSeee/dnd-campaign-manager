"""RSVP click handler — state transitions, count refresh, maybe-not-allowed."""
from datetime import datetime, timezone

from mmo_maid_sdk.testing import make_event

from plugin_module.core import ids
from plugin_module.handlers import rsvp as rsvp_handler


def _make_rsvp_event(*, session_id: int, status: str, user_id: str = "201"):
    return make_event(
        "interaction_create",
        interaction_type=3,
        custom_id=ids.rsvp_id(session_id, status),
        user_id=user_id,
        member={"user": {"id": user_id}, "roles": [], "permissions": "0"},
    )


def _stub_session_lookups(ctx, sample_campaign, sample_settings, *, maybe_allowed=True, session_status="scheduled"):
    sample_settings = dict(sample_settings)
    sample_settings["maybe_allowed"] = maybe_allowed

    session_row = {
        "id": 100, "campaign_id": 42, "discord_srv_id": 999,
        "session_number": 5, "title": "Test", "notes_for_players": "",
        "starts_at": datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc),
        "duration_minutes": 240, "status": session_status,
        "announce_channel_id": 12345, "announce_message_id": 99999,
        "series_id": None, "recurrence_rule": None,
        "next_reminder_due_at": None, "reminder_offsets_sent": [],
        "created_by_user_id": 1001,
    }

    def _q1(sql_sub: str, row):
        ctx.sql.on_query_one(sql_sub, lambda params: row)

    _q1("FROM dnd_sessions", session_row)
    _q1("FROM dnd_campaigns", sample_campaign)
    _q1("FROM dnd_campaign_settings", sample_settings)


def test_rsvp_attending_records_and_refreshes(ctx, sample_campaign, sample_settings):
    _stub_session_lookups(ctx, sample_campaign, sample_settings)
    # rsvps.counts_by_status / list_user_ids_by_status will hit ctx.sql.query
    ctx.sql.on_query("FROM dnd_session_rsvps WHERE session_id = %s GROUP BY status",
                     lambda p: [{"status": "attending", "cnt": 1}])
    ctx.sql.on_query("FROM dnd_session_rsvps WHERE session_id = %s AND status",
                     lambda p: [{"user_id": 201}] if p[1] == "attending" else [])

    event = _make_rsvp_event(session_id=100, status="attending")
    event["interaction_id"] = "interaction_99"
    ctx._current_interaction_id = "interaction_99"

    rsvp_handler.handle_rsvp(ctx, event)

    # Deferred, then followup
    assert len(ctx.interaction.defers) == 1
    assert ctx.interaction.defers[0]["ephemeral"] is True
    assert len(ctx.interaction.followups) == 1
    assert "attending" in ctx.interaction.followups[0]["content"].lower()

    # Embed was refreshed via edit_message
    assert len(ctx.discord.messages_edited) == 1
    edit = ctx.discord.messages_edited[0]
    assert edit["channel_id"] == "12345"
    assert edit["message_id"] == "99999"


def test_rsvp_maybe_rejected_when_disabled(ctx, sample_campaign, sample_settings):
    _stub_session_lookups(ctx, sample_campaign, sample_settings, maybe_allowed=False)

    event = _make_rsvp_event(session_id=100, status="maybe")
    event["interaction_id"] = "i1"
    ctx._current_interaction_id = "i1"

    rsvp_handler.handle_rsvp(ctx, event)

    # Should have been rejected with an ephemeral response, no defer
    assert ctx.interaction.defers == []
    assert len(ctx.interaction.responses) == 1
    assert "maybe" in ctx.interaction.responses[0]["content"].lower()
    assert ctx.interaction.responses[0]["ephemeral"] is True
    # And no embed refresh
    assert ctx.discord.messages_edited == []


def test_rsvp_blocked_when_session_cancelled(ctx, sample_campaign, sample_settings):
    _stub_session_lookups(ctx, sample_campaign, sample_settings, session_status="cancelled")
    event = _make_rsvp_event(session_id=100, status="attending")
    event["interaction_id"] = "i1"
    ctx._current_interaction_id = "i1"

    rsvp_handler.handle_rsvp(ctx, event)

    assert ctx.interaction.defers == []
    assert len(ctx.interaction.responses) == 1
    assert "closed" in ctx.interaction.responses[0]["content"].lower()


def test_rsvp_handles_missing_session(ctx):
    ctx.sql.on_query_one("FROM dnd_sessions", lambda p: None)
    event = _make_rsvp_event(session_id=999, status="attending")
    event["interaction_id"] = "i1"
    ctx._current_interaction_id = "i1"

    rsvp_handler.handle_rsvp(ctx, event)
    assert len(ctx.interaction.responses) == 1
    assert "no longer available" in ctx.interaction.responses[0]["content"].lower()


def test_rsvp_handler_ignores_unrelated_custom_ids(ctx):
    event = make_event(
        "interaction_create",
        interaction_type=3,
        custom_id="some_other_plugin:btn_click",
        member={"user": {"id": "1"}, "roles": [], "permissions": "0"},
    )
    rsvp_handler.handle_rsvp(ctx, event)
    # Decorated wrapper filters by prefix, but the handler itself is being
    # called directly — verify parse_rsvp_id returns None and we early-out.
    assert ctx.interaction.responses == []
    assert ctx.discord.messages_edited == []
