"""Versioned custom_id helpers — encoding and parsing must be round-trip stable."""
from plugin_module.core import ids


def test_rsvp_round_trip():
    cid = ids.rsvp_id(42, "attending")
    assert cid.startswith("dnd_v1:rsvp:")
    parsed = ids.parse_rsvp_id(cid)
    assert parsed == (42, "attending")


def test_rsvp_parse_rejects_wrong_prefix():
    assert ids.parse_rsvp_id("dnd_v1:other:42:attending") is None
    assert ids.parse_rsvp_id("dnd_v2:rsvp:42:attending") is None
    assert ids.parse_rsvp_id("") is None


def test_recap_modal_round_trip():
    cid = ids.recap_modal_id(100)
    assert ids.parse_recap_modal_id(cid) == 100


def test_recap_post_id_parses_with_single_int_helper():
    cid = ids.recap_post_id(7)
    assert ids.parse_single_int_after(cid, "recap_post") == 7


def test_picker_round_trip():
    cid = ids.picker_id(ids.PICKER_CAMPAIGN_FOR_SETTINGS)
    parsed = ids.parse_picker_id(cid)
    assert parsed == ids.PICKER_CAMPAIGN_FOR_SETTINGS


def test_visibility_btn_round_trip():
    cid = ids.visibility_btn_id("quest_add", "dm_only", 42)
    parsed = ids.parse_visibility_btn_id(cid)
    assert parsed == ("quest_add", "dm_only", 42)


def test_modal_quest_add_round_trip():
    cid = ids.modal_quest_add_id(42, "public")
    assert ids.parse_modal_quest_add(cid) == (42, "public")


def test_modal_npc_add_round_trip():
    cid = ids.modal_npc_add_id(42, "partial")
    assert ids.parse_modal_npc_add(cid) == (42, "partial")


def test_modal_session_schedule_round_trip():
    cid = ids.modal_session_schedule_id(42)
    assert ids.parse_modal_session_schedule(cid) == 42


def test_modal_campaign_settings_round_trip():
    cid = ids.modal_campaign_settings_id(42)
    assert ids.parse_modal_campaign_settings(cid) == 42


def test_recurrence_picker_round_trip():
    cid = ids.recurrence_picker_id(42)
    assert ids.parse_recurrence_picker(cid) == 42


def test_all_custom_ids_within_discord_limit():
    """Discord enforces a 100-char limit on custom_ids."""
    samples = [
        ids.rsvp_id(99999999999999, "unavailable"),
        ids.recap_modal_id(99999999999999),
        ids.modal_npc_add_id(99999999999999, "dm_only"),
        ids.modal_quest_add_id(99999999999999, "public"),
        ids.visibility_btn_id("quest_add", "dm_only", 99999999999999),
        ids.picker_id(ids.PICKER_CAMPAIGN_FOR_SETTINGS),
    ]
    for cid in samples:
        assert len(cid) <= 100, f"custom_id too long: {cid} ({len(cid)} chars)"
