"""View Recap / View Campaign Info / View past recaps buttons."""
from mmo_maid_sdk.testing import make_event

from plugin_module.core import ids
from plugin_module.handlers import campaign as campaign_handler
from plugin_module.handlers import recap as recap_handler


def _player_event(custom_id):
    return make_event(
        "interaction_create",
        interaction_type=3,
        custom_id=custom_id,
        member={"user": {"id": "2002"}, "roles": [], "permissions": "0"},
    )


def _stub_campaign(ctx, campaign, settings):
    ctx.sql.on_query_one("FROM dnd_campaigns", lambda p: campaign)
    ctx.sql.on_query_one("FROM dnd_campaign_settings", lambda p: settings)


def test_view_campaign_info_button_renders_info_embed(ctx, sample_campaign, sample_settings):
    _stub_campaign(ctx, sample_campaign, sample_settings)
    ctx.sql.on_query("FROM dnd_party_members", lambda p: [])
    ctx.sql.on_query("FROM dnd_quests", lambda p: [])
    ctx.sql.on_query_one("FROM dnd_sessions", lambda p: None)

    campaign_handler.handle_view_campaign_info_button(
        ctx, _player_event(ids.view_campaign_info_id(42))
    )

    resp = ctx.interaction.responses[0]
    assert resp["ephemeral"] is True
    assert "Lost Mines" in resp["embeds"][0]["title"]


def test_view_campaign_recaps_button_lists_recaps(ctx, sample_campaign, sample_settings):
    _stub_campaign(ctx, sample_campaign, sample_settings)
    ctx.sql.on_query("FROM dnd_recaps", lambda p: [
        {"id": 11, "session_id": 100, "title": "Session 5 recap",
         "summary": "We won.", "posted_at": None, "posted_channel_id": None,
         "posted_message_id": None, "session_number": 5},
    ])

    campaign_handler.handle_view_campaign_recaps_button(
        ctx, _player_event(ids.view_campaign_recaps_id(42))
    )

    resp = ctx.interaction.responses[0]
    assert resp["ephemeral"] is True
    assert "Past recaps" in resp["embeds"][0]["title"]
    # Should have at least one View button
    assert resp["components"], "expected component row with View buttons"


def test_recap_view_button_renders_recap_to_clicker(ctx, sample_campaign):
    """Player clicks 'View: Session 5 recap' → ephemeral recap embed."""
    posted_recap = {
        "id": 11, "session_id": 100, "campaign_id": 42, "discord_srv_id": 999,
        "title": "Session 5 recap", "summary": "We delved into the tomb.",
        "highlights": "Aragorn crit twice.", "loot": None, "cliffhanger": None,
        "dm_notes": None, "status": "posted",
        "posted_channel_id": 12346, "posted_message_id": 99998,
        "author_user_id": 1001,
    }
    session_row = {
        "id": 100, "campaign_id": 42, "discord_srv_id": 999,
        "session_number": 5, "title": "The Tomb",
        "starts_at": None, "duration_minutes": 240, "status": "completed",
        "reminder_offsets_sent": [],
    }
    # Query orders: get_recap → get_session → get_campaign
    ctx.sql.on_query_one("FROM dnd_recaps", lambda p: posted_recap)
    # Both session lookup and campaign lookup are query_one + FROM dnd_X.
    # The recap lookup must match first; route by table name.
    def _q1(sql, params=None):
        if "FROM dnd_recaps" in sql:
            return posted_recap
        if "FROM dnd_sessions" in sql:
            return session_row
        if "FROM dnd_campaigns" in sql:
            return sample_campaign
        return None
    ctx.sql.query_one = _q1

    recap_handler.handle_recap_view(
        ctx, _player_event(ids.recap_view_id(11))
    )

    resp = ctx.interaction.responses[0]
    assert resp["ephemeral"] is True
    assert "Session 5 recap" in resp["embeds"][0]["title"]


def test_recap_view_unknown_recap_responds_gracefully(ctx):
    ctx.sql.on_query_one("FROM dnd_recaps", lambda p: None)
    recap_handler.handle_recap_view(
        ctx, _player_event(ids.recap_view_id(999))
    )
    assert "no longer available" in ctx.interaction.responses[0]["content"].lower()


def test_recap_view_skips_draft(ctx, sample_campaign):
    draft = {
        "id": 11, "session_id": 100, "campaign_id": 42, "discord_srv_id": 999,
        "title": "WIP", "summary": "draft text",
        "highlights": None, "loot": None, "cliffhanger": None, "dm_notes": None,
        "status": "draft",
        "posted_channel_id": None, "posted_message_id": None, "author_user_id": 1001,
    }
    ctx.sql.on_query_one("FROM dnd_recaps", lambda p: draft)
    recap_handler.handle_recap_view(
        ctx, _player_event(ids.recap_view_id(11))
    )
    assert "no longer available" in ctx.interaction.responses[0]["content"].lower()
