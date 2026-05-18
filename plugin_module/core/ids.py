"""Versioned custom_id helpers.

Discord custom_ids are limited to 100 chars. We use the `dnd_v1:` prefix
everywhere so that on a future major schema change we bump the version and
old buttons get routed to a friendly "expired — please re-run" handler.

ID shape: ``<prefix>:<scope>:<id>[:<extra>]``
- scope identifies the handler family (rsvp, recap, cancel, picker, etc.)
- id is the relevant database row id
- extra carries optional state (e.g. status name)
"""
from typing import Optional, Tuple

from plugin_module.constants import CUSTOM_ID_PREFIX


def _build(*parts: str) -> str:
    raw = ":".join(str(p) for p in (CUSTOM_ID_PREFIX, *parts))
    return raw[:100]


def _split(custom_id: str, expected_prefix: str) -> list:
    if not custom_id or not custom_id.startswith(f"{CUSTOM_ID_PREFIX}:{expected_prefix}:"):
        return []
    return custom_id.split(":")


# ── RSVP ──────────────────────────────────────────────────────────────────


def rsvp_id(session_id: int, status: str) -> str:
    return _build("rsvp", session_id, status)


def parse_rsvp_id(custom_id: str) -> Optional[Tuple[int, str]]:
    parts = _split(custom_id, "rsvp")
    if len(parts) != 4:
        return None
    try:
        return int(parts[2]), parts[3]
    except ValueError:
        return None


RSVP_PREFIX = f"{CUSTOM_ID_PREFIX}:rsvp:"


# ── Recap workflow ────────────────────────────────────────────────────────


def recap_modal_id(session_id: int) -> str:
    return _build("recap_modal", session_id)


def parse_recap_modal_id(custom_id: str) -> Optional[int]:
    parts = _split(custom_id, "recap_modal")
    if len(parts) != 3:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


def recap_post_id(recap_id: int) -> str:
    return _build("recap_post", recap_id)


def recap_keep_id(recap_id: int) -> str:
    return _build("recap_keep", recap_id)


def recap_dmnotes_id(recap_id: int) -> str:
    return _build("recap_dmnotes", recap_id)


def recap_dmnotes_modal_id(recap_id: int) -> str:
    return _build("recap_dmnotes_modal", recap_id)


def recap_create_btn_id(session_id: int) -> str:
    """Button shown on the session announcement embed after the session ends."""
    return _build("recap_create", session_id)


def recap_view_id(recap_id: int) -> str:
    """View the full body of a posted recap, ephemerally."""
    return _build("recap_view", recap_id)


def view_campaign_info_id(campaign_id: int) -> str:
    """Open an ephemeral campaign info embed from anywhere."""
    return _build("view_camp", campaign_id)


def view_campaign_recaps_id(campaign_id: int) -> str:
    """Open an ephemeral list of past recaps for the campaign."""
    return _build("view_recaps", campaign_id)


def suggest_alt_time_btn_id(session_id: int) -> str:
    """Button on the session announce embed (gated by setting)."""
    return _build("alt_time", session_id)


def suggest_alt_time_modal_id(session_id: int) -> str:
    return _build("modal", "alt_time", session_id)


def parse_modal_alt_time(custom_id: str) -> Optional[int]:
    parts = _split(custom_id, "modal")
    if len(parts) != 4 or parts[2] != "alt_time":
        return None
    try:
        return int(parts[3])
    except ValueError:
        return None


def parse_single_int_after(custom_id: str, scope: str) -> Optional[int]:
    parts = _split(custom_id, scope)
    if len(parts) != 3:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


# ── Cancel confirmation ───────────────────────────────────────────────────


def cancel_confirm_id(session_id: int) -> str:
    return _build("cancel_confirm", session_id)


def cancel_keep_id(session_id: int) -> str:
    return _build("cancel_keep", session_id)


# ── Pickers (SelectMenus that route back into a flow) ─────────────────────


def picker_id(target: str) -> str:
    """target is e.g. 'campaign_for_settings', 'campaign_for_session_schedule', 'session_for_recap'."""
    return _build("picker", target)


def parse_picker_id(custom_id: str) -> Optional[str]:
    parts = _split(custom_id, "picker")
    if len(parts) != 3:
        return None
    return parts[2]


PICKER_PREFIX = f"{CUSTOM_ID_PREFIX}:picker:"


# Targets — keep this set small and stable
PICKER_CAMPAIGN_FOR_SETTINGS = "camp_settings"
PICKER_CAMPAIGN_FOR_INFO = "camp_info"
PICKER_CAMPAIGN_FOR_SESSION_SCHEDULE = "camp_session_sched"
PICKER_CAMPAIGN_FOR_QUEST_ADD = "camp_quest_add"
PICKER_CAMPAIGN_FOR_NPC_ADD = "camp_npc_add"
PICKER_CAMPAIGN_FOR_PARTY = "camp_party"
PICKER_CAMPAIGN_FOR_DMNOTE_ADD = "camp_dmnote_add"
PICKER_CAMPAIGN_FOR_DMNOTE_LIST = "camp_dmnote_list"
PICKER_CAMPAIGN_FOR_SESSION_LIST = "camp_session_list"
PICKER_SESSION_FOR_CANCEL = "sess_cancel"
PICKER_SESSION_FOR_RECAP = "sess_recap"
PICKER_SESSION_FOR_ATTENDANCE = "sess_attend"
PICKER_QUEST_FOR_UPDATE = "quest_update"


# ── Visibility pickers (button row before a modal) ────────────────────────


def visibility_btn_id(target: str, visibility: str, campaign_id: int) -> str:
    """target='quest_add' or 'npc_add'; visibility one of public/partial/dm_only."""
    return _build("vis", target, visibility, campaign_id)


def parse_visibility_btn_id(custom_id: str):
    parts = _split(custom_id, "vis")
    if len(parts) != 5:
        return None
    try:
        return parts[2], parts[3], int(parts[4])
    except ValueError:
        return None


VIS_PREFIX = f"{CUSTOM_ID_PREFIX}:vis:"


# ── Modal IDs ─────────────────────────────────────────────────────────────


MODAL_CAMPAIGN_CREATE = _build("modal", "campaign_create")
MODAL_CAMPAIGN_SETTINGS = "modal_settings"  # built dynamically with campaign_id below


def modal_campaign_settings_id(campaign_id: int) -> str:
    return _build("modal", "campaign_settings", campaign_id)


def parse_modal_campaign_settings(custom_id: str) -> Optional[int]:
    parts = _split(custom_id, "modal")
    if len(parts) != 4 or parts[2] != "campaign_settings":
        return None
    try:
        return int(parts[3])
    except ValueError:
        return None


# ── Settings panel buttons / modals (button-driven settings refactor) ────


def settings_edit_btn_id(section: str, campaign_id: int) -> str:
    """section ∈ {channels, roles, reminders, defaults, toggles, npc_vis}."""
    return _build("settings_edit", section, campaign_id)


def parse_settings_edit_btn(custom_id: str):
    parts = _split(custom_id, "settings_edit")
    if len(parts) != 4:
        return None
    try:
        return parts[2], int(parts[3])
    except ValueError:
        return None


def modal_settings_section_id(section: str, campaign_id: int) -> str:
    return _build("modal", f"settings_{section}", campaign_id)


def parse_modal_settings_section(custom_id: str):
    parts = _split(custom_id, "modal")
    if len(parts) != 4 or not parts[2].startswith("settings_"):
        return None
    section = parts[2][len("settings_"):]
    try:
        return section, int(parts[3])
    except ValueError:
        return None


def settings_toggle_btn_id(toggle: str, campaign_id: int) -> str:
    """toggle ∈ {rsvp_required, maybe_allowed, alternate_times_allowed,
    recap_draft_first, quest_log_public, ping_on_reminders}."""
    return _build("toggle", toggle, campaign_id)


def parse_settings_toggle_btn(custom_id: str):
    parts = _split(custom_id, "toggle")
    if len(parts) != 4:
        return None
    try:
        return parts[2], int(parts[3])
    except ValueError:
        return None


def settings_npc_vis_select_id(campaign_id: int) -> str:
    return _build("npc_vis_set", campaign_id)


def parse_settings_npc_vis_select(custom_id: str) -> Optional[int]:
    parts = _split(custom_id, "npc_vis_set")
    if len(parts) != 3:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None


def settings_back_btn_id(campaign_id: int) -> str:
    """Return-to-summary button shown in the toggles ephemeral and NPC select."""
    return _build("settings_back", campaign_id)


def modal_session_schedule_id(campaign_id: int) -> str:
    return _build("modal", "session_schedule", campaign_id)


def parse_modal_session_schedule(custom_id: str) -> Optional[int]:
    parts = _split(custom_id, "modal")
    if len(parts) != 4 or parts[2] != "session_schedule":
        return None
    try:
        return int(parts[3])
    except ValueError:
        return None


def modal_quest_add_id(campaign_id: int, visibility: str) -> str:
    return _build("modal", "quest_add", campaign_id, visibility)


def parse_modal_quest_add(custom_id: str):
    parts = _split(custom_id, "modal")
    if len(parts) != 5 or parts[2] != "quest_add":
        return None
    try:
        return int(parts[3]), parts[4]
    except ValueError:
        return None


def modal_quest_update_id(quest_id: int) -> str:
    return _build("modal", "quest_update", quest_id)


def parse_modal_quest_update(custom_id: str) -> Optional[int]:
    parts = _split(custom_id, "modal")
    if len(parts) != 4 or parts[2] != "quest_update":
        return None
    try:
        return int(parts[3])
    except ValueError:
        return None


def modal_npc_add_id(campaign_id: int, visibility: str) -> str:
    return _build("modal", "npc_add", campaign_id, visibility)


def parse_modal_npc_add(custom_id: str):
    parts = _split(custom_id, "modal")
    if len(parts) != 5 or parts[2] != "npc_add":
        return None
    try:
        return int(parts[3]), parts[4]
    except ValueError:
        return None


def modal_dmnote_add_id(campaign_id: int) -> str:
    return _build("modal", "dmnote_add", campaign_id)


def parse_modal_dmnote_add(custom_id: str) -> Optional[int]:
    parts = _split(custom_id, "modal")
    if len(parts) != 4 or parts[2] != "dmnote_add":
        return None
    try:
        return int(parts[3])
    except ValueError:
        return None


# Recurrence picker shown as an ephemeral followup after schedule modal submit
def recurrence_picker_id(session_id: int) -> str:
    return _build("recurrence", session_id)


def parse_recurrence_picker(custom_id: str) -> Optional[int]:
    parts = _split(custom_id, "recurrence")
    if len(parts) != 3:
        return None
    try:
        return int(parts[2])
    except ValueError:
        return None
