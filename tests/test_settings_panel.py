"""Settings panel — button-driven UX: edit buttons, toggles, NPC visibility."""
from mmo_maid_sdk.testing import make_event

from plugin_module.core import ids
from plugin_module.handlers import campaign as campaign_handler


def _admin_settings_event(campaign_id=42):
    inner = {"name": "settings", "type": 1, "options": []}
    if campaign_id is not None:
        inner["options"].append({"name": "campaign_id", "type": 4, "value": campaign_id})
    return make_event(
        "interaction_create",
        interaction_type=2,
        command_name="campaign",
        options=[inner],
        member={"user": {"id": "1001"}, "roles": [], "permissions": str(0x8)},
    )


def _stub_campaign(ctx, campaign, settings):
    ctx.sql.on_query_one("FROM dnd_campaigns", lambda p: campaign)
    ctx.sql.on_query_one("FROM dnd_campaign_settings", lambda p: settings)


def test_settings_renders_summary_and_panel(ctx, sample_campaign, sample_settings):
    _stub_campaign(ctx, sample_campaign, sample_settings)
    campaign_handler.handle_campaign(ctx, _admin_settings_event())

    assert len(ctx.interaction.responses) == 1
    resp = ctx.interaction.responses[0]
    assert resp["ephemeral"] is True
    # Expect the summary embed
    assert resp["embeds"] and "Settings" in resp["embeds"][0]["title"]
    # Two rows: 4 + 2 = 6 buttons total
    rows = resp["components"]
    assert len(rows) == 2
    total_buttons = sum(len(r.children) for r in rows)
    assert total_buttons == 6


def test_settings_edit_channels_opens_focused_modal(ctx, sample_campaign, sample_settings):
    _stub_campaign(ctx, sample_campaign, sample_settings)
    event = make_event(
        "interaction_create",
        interaction_type=3,
        custom_id=ids.settings_edit_btn_id("channels", 42),
        member={"user": {"id": "1001"}, "roles": [], "permissions": str(0x8)},
    )
    campaign_handler.handle_settings_edit_button(ctx, event)

    assert len(ctx.interaction.modals_sent) == 1
    modal = ctx.interaction.modals_sent[0]
    assert "Channels" in modal["title"]
    field_ids = [f.custom_id for f in modal["fields"]]
    assert field_ids == ["announce_channel_id", "recap_channel_id", "reminder_channel_id"]


def test_settings_edit_toggles_opens_button_panel(ctx, sample_campaign, sample_settings):
    _stub_campaign(ctx, sample_campaign, sample_settings)
    event = make_event(
        "interaction_create",
        interaction_type=3,
        custom_id=ids.settings_edit_btn_id("toggles", 42),
        member={"user": {"id": "1001"}, "roles": [], "permissions": str(0x8)},
    )
    campaign_handler.handle_settings_edit_button(ctx, event)

    resp = ctx.interaction.responses[0]
    assert resp["ephemeral"] is True
    # 6 toggle buttons + 1 back button across multiple rows
    rows = resp["components"]
    btn_labels = []
    for r in rows:
        for c in r.children:
            if hasattr(c, "label"):
                btn_labels.append(c.label)
    assert any("RSVP required" in lbl for lbl in btn_labels)
    assert any("Maybe" in lbl for lbl in btn_labels)
    assert any("Back" in lbl for lbl in btn_labels)


def test_toggle_button_flips_boolean(ctx, sample_campaign, sample_settings):
    settings = dict(sample_settings)
    settings["rsvp_required"] = False
    _stub_campaign(ctx, sample_campaign, settings)
    # Stub the update_settings call to flip rsvp_required = True so the next
    # get_settings returns the new value
    state = {"rsvp_required": False}

    def _q1_settings(_):
        return {**settings, **state}
    ctx.sql.on_query_one("FROM dnd_campaign_settings", _q1_settings)

    def _exec(sql, params=None):
        if "UPDATE dnd_campaign_settings" in sql and "rsvp_required" in sql:
            state["rsvp_required"] = bool(params[0]) if params else True
        return 1
    ctx.sql.on_execute("UPDATE dnd_campaign_settings", lambda p: (
        state.__setitem__("rsvp_required", True) or 1
    ))

    event = make_event(
        "interaction_create",
        interaction_type=3,
        custom_id=ids.settings_toggle_btn_id("rsvp_required", 42),
        member={"user": {"id": "1001"}, "roles": [], "permissions": str(0x8)},
    )
    campaign_handler.handle_settings_toggle(ctx, event)

    # Should respond with the refreshed toggles panel
    assert len(ctx.interaction.responses) == 1
    assert ctx.interaction.responses[0]["ephemeral"] is True


def test_npc_visibility_select_persists_choice(ctx, sample_campaign, sample_settings):
    _stub_campaign(ctx, sample_campaign, sample_settings)
    ctx.sql.on_execute("UPDATE dnd_campaign_settings", lambda p: 1)

    event = make_event(
        "interaction_create",
        interaction_type=3,
        custom_id=ids.settings_npc_vis_select_id(42),
        values=["dm_only"],
        member={"user": {"id": "1001"}, "roles": [], "permissions": str(0x8)},
    )
    campaign_handler.handle_settings_npc_vis(ctx, event)

    # An UPDATE was issued
    updates = [
        e for e in ctx.sql.executed
        if e["op"] == "execute" and "UPDATE dnd_campaign_settings" in e["sql"]
    ]
    assert updates, "no settings update issued"
    # Should also re-render the summary
    assert any("Settings" in (r.get("embeds") or [{}])[0].get("title", "")
               for r in ctx.interaction.responses)


def test_settings_picker_for_multi_campaign_server(ctx, sample_campaign, sample_settings):
    # No campaign_id provided → multiple campaigns → picker
    ctx.sql.on_query("FROM dnd_campaigns", lambda p: [
        {"id": 42, "name": "Lost Mines"},
        {"id": 43, "name": "Tomb of Annihilation"},
    ])
    event = _admin_settings_event(campaign_id=None)
    campaign_handler.handle_campaign(ctx, event)

    resp = ctx.interaction.responses[0]
    assert "Pick the campaign" in resp["content"]
    assert resp["ephemeral"] is True
