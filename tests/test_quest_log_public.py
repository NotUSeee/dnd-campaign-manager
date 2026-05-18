"""quest_log_public=False must hide ALL quests from non-DM viewers."""
from mmo_maid_sdk.testing import make_event

from plugin_module.handlers import quest as quest_handler


def _player_list_event():
    return make_event(
        "interaction_create",
        interaction_type=2,
        command_name="quest",
        options=[{"name": "list", "type": 1, "options": [
            {"name": "campaign_id", "type": 4, "value": 42}
        ]}],
        member={"user": {"id": "2002"}, "roles": [], "permissions": "0"},
    )


def _dm_list_event():
    return make_event(
        "interaction_create",
        interaction_type=2,
        command_name="quest",
        options=[{"name": "list", "type": 1, "options": [
            {"name": "campaign_id", "type": 4, "value": 42}
        ]}],
        member={"user": {"id": "3003"}, "roles": ["55555"], "permissions": "0"},
    )


def _stub(ctx, campaign, settings, quests):
    ctx.sql.on_query_one("FROM dnd_campaigns", lambda p: campaign)
    ctx.sql.on_query_one("FROM dnd_campaign_settings", lambda p: settings)
    ctx.sql.on_query("FROM dnd_quests", lambda p: quests)


def test_player_sees_nothing_when_quest_log_private(ctx, sample_campaign, sample_settings):
    settings = dict(sample_settings)
    settings["quest_log_public"] = False
    _stub(ctx, sample_campaign, settings, [
        {"id": 1, "title": "Find the artifact", "status": "active", "visibility": "public"},
    ])

    quest_handler.handle_quest(ctx, _player_list_event())

    assert len(ctx.interaction.responses) == 1
    resp = ctx.interaction.responses[0]
    assert resp["ephemeral"] is True
    desc = resp["embeds"][0]["description"]
    assert "DM-only" in desc


def test_dm_still_sees_quests_when_log_private(ctx, sample_campaign, sample_settings):
    settings = dict(sample_settings)
    settings["quest_log_public"] = False
    _stub(ctx, sample_campaign, settings, [
        {"id": 1, "title": "Find the artifact", "status": "active", "visibility": "public"},
    ])

    quest_handler.handle_quest(ctx, _dm_list_event())

    # DM should see the regular list embed (which renders fields per status)
    embed = ctx.interaction.responses[0]["embeds"][0]
    assert "Quest log" in embed["title"]
    assert embed.get("fields"), "expected fielded list, got empty embed"


def test_player_sees_public_quests_when_log_public(ctx, sample_campaign, sample_settings):
    settings = dict(sample_settings)
    settings["quest_log_public"] = True
    _stub(ctx, sample_campaign, settings, [
        {"id": 1, "title": "Find the artifact", "status": "active", "visibility": "public"},
    ])

    quest_handler.handle_quest(ctx, _player_list_event())

    embed = ctx.interaction.responses[0]["embeds"][0]
    assert embed.get("fields"), "expected fielded list for player"
