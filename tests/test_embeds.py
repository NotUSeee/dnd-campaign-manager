"""Embed builders — snapshot the dict shape for the key embeds."""
from datetime import datetime, timezone

from plugin_module.constants import COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING
from plugin_module.ui import embeds


def _campaign():
    return {
        "id": 42,
        "name": "Lost Mines",
        "party_name": "The Lost Mines Crew",
        "system": "D&D 5e",
        "description": "Phandelver",
        "timezone": "UTC",
        "owner_user_id": 1001,
        "status": "active",
    }


def _session():
    return {
        "id": 100,
        "session_number": 5,
        "title": "Into the Cragmaw Hideout",
        "starts_at": datetime(2026, 6, 16, 19, 0, tzinfo=timezone.utc),
        "duration_minutes": 240,
        "status": "scheduled",
        "campaign_id": 42,
        "announce_channel_id": 12345,
        "notes_for_players": "Bring rations.",
    }


def test_session_announce_embed_has_rsvp_fields():
    embed = embeds.session_announce_embed(
        campaign=_campaign(),
        session=_session(),
        rsvp_counts={"attending": 3, "maybe": 1, "unavailable": 0},
        attendee_user_ids=[201, 202, 203],
        maybe_user_ids=[204],
        unavailable_user_ids=[],
    )
    assert "Into the Cragmaw Hideout" in embed["title"]
    assert embed["color"] == COLOR_PRIMARY
    field_names = [f["name"] for f in embed["fields"]]
    assert any("Attending (3)" in n for n in field_names)
    assert any("Maybe (1)" in n for n in field_names)
    assert any("Unavailable (0)" in n for n in field_names)


def test_session_announce_embed_for_cancelled_session_is_muted():
    s = _session()
    s["status"] = "cancelled"
    embed = embeds.session_announce_embed(
        campaign=_campaign(), session=s,
        rsvp_counts={"attending": 0, "maybe": 0, "unavailable": 0},
        attendee_user_ids=[], maybe_user_ids=[], unavailable_user_ids=[],
    )
    assert "CANCELLED" in embed["description"] or "🛑" in embed["title"]


def test_reminder_embed_uses_warning_color():
    embed = embeds.session_reminder_embed(
        campaign=_campaign(), session=_session(), offset_minutes=15
    )
    assert embed["color"] == COLOR_WARNING
    assert "15m" in embed["title"]


def test_recap_preview_embed_has_summary_field():
    recap = {
        "id": 1, "session_id": 100, "campaign_id": 42,
        "title": "Session 5 recap", "summary": "We explored the cave.",
        "highlights": None, "loot": None, "cliffhanger": "A trapdoor opens.",
    }
    embed = embeds.recap_preview_embed(recap, _session(), _campaign())
    field_names = [f["name"] for f in embed["fields"]]
    assert "Summary" in field_names
    assert "Cliffhanger" in field_names


def test_quest_list_embed_groups_by_status():
    quests = [
        {"id": 1, "title": "A", "status": "active", "visibility": "public"},
        {"id": 2, "title": "B", "status": "completed", "visibility": "public"},
        {"id": 3, "title": "C", "status": "active", "visibility": "dm_only"},
    ]
    embed = embeds.quest_list_embed(_campaign(), quests, viewer_is_dm=True)
    field_names = [f["name"] for f in embed["fields"]]
    assert any("Active" in n for n in field_names)
    assert any("Completed" in n for n in field_names)


def test_npc_list_embed_hides_secrets_from_players():
    npcs = [
        {"id": 1, "name": "Sildar", "role": "Knight", "location": "Phandalin",
         "public_notes": "Helpful npc", "visibility": "public"},
    ]
    embed = embeds.npc_list_embed(_campaign(), npcs, viewer_is_dm=False)
    # players see public_notes but never secret_notes
    assert "Helpful npc" in embed["description"]
    assert "secret" not in embed["description"].lower()


def test_dmnote_added_embed_carries_dm_only_footer():
    note = {"id": 1, "title": "Plot hooks", "body": "Cult plans"}
    embed = embeds.dmnote_added_embed(note)
    assert "DM-only" in embed["footer"]["text"] or "players cannot see" in embed["footer"]["text"].lower()


def test_party_roster_embed_empty_says_so():
    embed = embeds.party_roster_embed(_campaign(), [])
    assert "Nobody" in embed["description"]


def test_session_cancel_confirm_embed_is_warning():
    embed = embeds.session_cancel_confirm_embed(_session())
    assert embed["color"] == COLOR_WARNING
    assert "Cancel" in embed["title"]
