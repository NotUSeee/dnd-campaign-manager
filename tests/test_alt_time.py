"""Suggest-alternate-time flow — button gated by setting, modal posts publicly."""
from datetime import datetime, timezone

from mmo_maid_sdk.testing import make_event

from plugin_module.core import ids
from plugin_module.handlers import session as session_handler


def _player_event(custom_id):
    return make_event(
        "interaction_create",
        interaction_type=3,
        custom_id=custom_id,
        member={"user": {"id": "2002"}, "roles": [], "permissions": "0"},
    )


def _modal_submit(custom_id, modal_values):
    return make_event(
        "interaction_create",
        interaction_type=5,
        custom_id=custom_id,
        modal_values=modal_values,
        member={"user": {"id": "2002"}, "roles": [], "permissions": "0"},
    )


def _session_row(status="scheduled"):
    return {
        "id": 100, "campaign_id": 42, "discord_srv_id": 999,
        "session_number": 5, "title": "Test",
        "starts_at": datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc),
        "duration_minutes": 240, "status": status,
        "announce_channel_id": 12345, "announce_message_id": 99999,
        "series_id": None, "recurrence_rule": None,
        "next_reminder_due_at": None, "reminder_offsets_sent": [],
        "created_by_user_id": 1001,
    }


def _stub(ctx, campaign, settings, session, *, allow_alt):
    settings = dict(settings)
    settings["alternate_times_allowed"] = allow_alt

    def _q1(sql, params=None):
        if "FROM dnd_sessions" in sql:
            return session
        if "FROM dnd_campaigns" in sql:
            return campaign
        if "FROM dnd_campaign_settings" in sql:
            return settings
        return None
    ctx.sql.query_one = _q1


def test_alt_time_button_rejected_when_setting_off(ctx, sample_campaign, sample_settings):
    _stub(ctx, sample_campaign, sample_settings, _session_row(), allow_alt=False)
    session_handler.handle_alt_time_button(
        ctx, _player_event(ids.suggest_alt_time_btn_id(100))
    )
    resp = ctx.interaction.responses[0]
    assert "isn't accepting" in resp["content"]
    assert resp["ephemeral"] is True
    assert ctx.interaction.modals_sent == []


def test_alt_time_button_opens_modal_when_setting_on(ctx, sample_campaign, sample_settings):
    _stub(ctx, sample_campaign, sample_settings, _session_row(), allow_alt=True)
    session_handler.handle_alt_time_button(
        ctx, _player_event(ids.suggest_alt_time_btn_id(100))
    )
    assert len(ctx.interaction.modals_sent) == 1
    assert "Propose" in ctx.interaction.modals_sent[0]["title"]


def test_alt_time_button_rejected_on_cancelled_session(ctx, sample_campaign, sample_settings):
    _stub(ctx, sample_campaign, sample_settings, _session_row(status="cancelled"), allow_alt=True)
    session_handler.handle_alt_time_button(
        ctx, _player_event(ids.suggest_alt_time_btn_id(100))
    )
    assert "no longer open" in ctx.interaction.responses[0]["content"]


def test_alt_time_modal_submit_posts_proposal(ctx, sample_campaign, sample_settings):
    _stub(ctx, sample_campaign, sample_settings, _session_row(), allow_alt=True)
    event = _modal_submit(
        ids.suggest_alt_time_modal_id(100),
        {"date": "2026-06-23", "time_local": "20:00", "reason": "work conflict"},
    )
    session_handler.handle_alt_time_modal(ctx, event)

    # Public message posted to announce channel
    assert len(ctx.discord.messages_sent) == 1
    msg = ctx.discord.messages_sent[0]
    assert msg["channel_id"] == "12345"
    embed = msg["embeds"][0]
    assert "Alternate time" in embed["title"]

    # Ephemeral confirmation
    resp = ctx.interaction.responses[0]
    assert resp["ephemeral"] is True
    assert "posted" in resp["content"].lower()


def test_alt_time_modal_rejects_bad_date(ctx, sample_campaign, sample_settings):
    _stub(ctx, sample_campaign, sample_settings, _session_row(), allow_alt=True)
    event = _modal_submit(
        ids.suggest_alt_time_modal_id(100),
        {"date": "tomorrow", "time_local": "20:00", "reason": ""},
    )
    session_handler.handle_alt_time_modal(ctx, event)

    assert ctx.discord.messages_sent == []
    assert "parse" in ctx.interaction.responses[0]["content"].lower()
