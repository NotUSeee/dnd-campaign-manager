"""Guarantee: /dmnotes flows never call ctx.discord.send_message.

If a future change accidentally adds a public message path in the notes
handler, this suite will catch it.
"""
from mmo_maid_sdk.testing import make_event

from plugin_module.core import ids
from plugin_module.handlers import notes as notes_handler


def _dm_event(*, sub: str, campaign_id=42):
    inner = {"name": sub, "type": 1, "options": []}
    if campaign_id is not None:
        inner["options"].append({"name": "campaign_id", "type": 4, "value": campaign_id})
    return make_event(
        "interaction_create",
        interaction_type=2,
        command_name="dmnotes",
        options=[inner],
        member={
            "user": {"id": "3003"},
            "roles": ["55555"],  # DM role
            "permissions": "0",
        },
    )


def _player_event(*, sub: str, campaign_id=42):
    inner = {"name": sub, "type": 1, "options": []}
    if campaign_id is not None:
        inner["options"].append({"name": "campaign_id", "type": 4, "value": campaign_id})
    return make_event(
        "interaction_create",
        interaction_type=2,
        command_name="dmnotes",
        options=[inner],
        member={
            "user": {"id": "2002"},
            "roles": [],
            "permissions": "0",
        },
    )


def _stub_campaign_lookups(ctx, sample_campaign, sample_settings):
    def _q1(sql_sub, row):
        ctx.sql.on_query_one(sql_sub, lambda p: row)

    _q1("FROM dnd_campaigns", sample_campaign)
    _q1("FROM dnd_campaign_settings", sample_settings)


def test_dmnotes_add_as_dm_sends_modal_no_public_message(ctx, sample_campaign, sample_settings):
    _stub_campaign_lookups(ctx, sample_campaign, sample_settings)
    notes_handler.handle_dmnotes(ctx, _dm_event(sub="add"))

    assert len(ctx.interaction.modals_sent) == 1
    assert ctx.discord.messages_sent == []


def test_dmnotes_add_modal_submit_responds_ephemeral_only(ctx, sample_campaign, sample_settings):
    _stub_campaign_lookups(ctx, sample_campaign, sample_settings)
    # Make the insert return a row
    ctx.sql.on_query(
        "INSERT INTO dnd_dm_notes",
        lambda p: [{"id": 7, "campaign_id": 42, "title": "Secret", "body": "X",
                    "author_user_id": 3003, "discord_srv_id": 999,
                    "created_at": None, "updated_at": None}],
    )

    event = make_event(
        "interaction_create",
        interaction_type=5,
        custom_id=ids.modal_dmnote_add_id(42),
        modal_values={"title": "Secret", "body": "Plot threads"},
        member={
            "user": {"id": "3003"},
            "roles": ["55555"],
            "permissions": "0",
        },
    )
    notes_handler.handle_dmnote_add_modal(ctx, event)

    # The handler responded ephemerally
    assert len(ctx.interaction.responses) == 1
    assert ctx.interaction.responses[0]["ephemeral"] is True
    # Critically — no public Discord message was sent
    assert ctx.discord.messages_sent == []


def test_dmnotes_list_as_player_denied(ctx, sample_campaign, sample_settings):
    _stub_campaign_lookups(ctx, sample_campaign, sample_settings)
    notes_handler.handle_dmnotes(ctx, _player_event(sub="list"))
    # Single ephemeral denial; never sent a public message
    assert any(
        "DM-only" in r["content"] for r in ctx.interaction.responses
    ), f"expected denial; got {ctx.interaction.responses}"
    assert all(r["ephemeral"] for r in ctx.interaction.responses)
    assert ctx.discord.messages_sent == []


def test_dmnotes_list_as_dm_lists_ephemerally(ctx, sample_campaign, sample_settings):
    _stub_campaign_lookups(ctx, sample_campaign, sample_settings)
    ctx.sql.on_query(
        "FROM dnd_dm_notes",
        lambda p: [{"id": 7, "title": "Plot", "body": "X" * 200, "author_user_id": 3003, "updated_at": None}],
    )
    notes_handler.handle_dmnotes(ctx, _dm_event(sub="list"))
    assert len(ctx.interaction.responses) == 1
    assert ctx.interaction.responses[0]["ephemeral"] is True
    assert ctx.discord.messages_sent == []
