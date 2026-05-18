"""Modal field-set builders.

Each builder returns a list of TextInput field objects suitable for passing
to `ctx.interaction.send_modal(fields=[...])`. Five fields max per modal.
"""
from typing import Any, Dict, List

from mmo_maid_sdk import TextInput


def campaign_create_fields() -> List[TextInput]:
    return [
        TextInput("Campaign Name", "name", placeholder="e.g. Curse of Strahd",
                  required=True, max_length=100),
        TextInput("Party Name", "party_name",
                  placeholder="e.g. The Lost Mines Crew (optional)",
                  required=False, max_length=80),
        TextInput("Game System", "system",
                  placeholder="D&D 5e, Pathfinder, custom… (default D&D 5e)",
                  required=False, max_length=60, value="D&D 5e"),
        TextInput("Description", "description", style="paragraph",
                  placeholder="A one-paragraph campaign pitch (optional)",
                  required=False, max_length=1000),
        TextInput("Timezone", "timezone",
                  placeholder="IANA tz, e.g. America/New_York (default UTC)",
                  required=False, max_length=40, value="UTC"),
    ]


# ── Settings panel focused modals (one per concern) ──────────────────────


def _val(v) -> str:
    return str(v) if v else ""


def settings_channels_fields(settings: Dict[str, Any]) -> List[TextInput]:
    return [
        TextInput("Announce channel ID", "announce_channel_id",
                  placeholder="Right-click channel → Copy ID (required)",
                  required=True, max_length=25,
                  value=_val(settings.get("announce_channel_id"))),
        TextInput("Recap channel ID", "recap_channel_id",
                  placeholder="Leave blank to reuse the announce channel",
                  required=False, max_length=25,
                  value=_val(settings.get("recap_channel_id"))),
        TextInput("Reminder channel ID", "reminder_channel_id",
                  placeholder="Leave blank to reuse the announce channel",
                  required=False, max_length=25,
                  value=_val(settings.get("reminder_channel_id"))),
    ]


def settings_roles_fields(settings: Dict[str, Any]) -> List[TextInput]:
    return [
        TextInput("DM role ID", "dm_role_id",
                  placeholder="Right-click role → Copy ID (optional)",
                  required=False, max_length=25,
                  value=_val(settings.get("dm_role_id"))),
        TextInput("Player role ID", "player_role_id",
                  placeholder="Pinged on reminders if you opt in (optional)",
                  required=False, max_length=25,
                  value=_val(settings.get("player_role_id"))),
    ]


def settings_reminders_fields(settings: Dict[str, Any]) -> List[TextInput]:
    offsets = settings.get("reminder_offsets_minutes") or [1440, 120, 15]
    offsets_str = ",".join(str(int(o)) for o in offsets)
    return [
        TextInput("Reminder offsets (minutes, comma-separated)",
                  "reminder_offsets",
                  placeholder="e.g. 1440,120,15 → 24h, 2h, 15m",
                  required=True, max_length=80,
                  value=offsets_str),
    ]


def settings_defaults_fields(settings: Dict[str, Any]) -> List[TextInput]:
    dow = settings.get("default_day_of_week")
    return [
        TextInput("Default day of week (0=Sun … 6=Sat)",
                  "default_day_of_week",
                  placeholder="Leave blank for none",
                  required=False, max_length=1,
                  value=str(dow) if dow is not None else ""),
        TextInput("Default start time (HH:MM, local)",
                  "default_time_local",
                  placeholder="e.g. 19:00 (leave blank for none)",
                  required=False, max_length=5,
                  value=_val(settings.get("default_time_local"))),
    ]


def session_schedule_fields(
    *,
    campaign_tz: str = "UTC",
    default_date: str = "",
    default_time_local: str = "",
    default_duration: int = 240,
) -> List[TextInput]:
    return [
        TextInput("Date (YYYY-MM-DD)", "date",
                  placeholder=default_date or "2026-06-15",
                  required=True, max_length=10,
                  value=default_date or ""),
        TextInput("Start time (HH:MM, 24h, in campaign timezone)",
                  "time_local",
                  placeholder=f"e.g. 19:00 ({campaign_tz})",
                  required=True, max_length=5,
                  value=default_time_local or ""),
        TextInput("Duration (minutes)", "duration_min",
                  placeholder=f"{default_duration} (default)", required=False,
                  value=str(default_duration), max_length=4),
        TextInput("Session title", "title",
                  placeholder="e.g. Into the Sunless Citadel (optional)",
                  required=False, max_length=120),
        TextInput("Notes for players", "notes_for_players", style="paragraph",
                  placeholder="Visible on the announcement (optional)",
                  required=False, max_length=1500),
    ]


def recap_fields(*, default_title: str = "") -> List[TextInput]:
    return [
        TextInput("Recap Title", "title",
                  placeholder=default_title or "e.g. Session 5 — The Tomb",
                  required=False, max_length=200,
                  value=default_title or ""),
        TextInput("Summary", "summary", style="paragraph",
                  placeholder="What happened this session?",
                  required=True, max_length=4000),
        TextInput("Highlights", "highlights", style="paragraph",
                  placeholder="Memorable moments (optional)",
                  required=False, max_length=2000),
        TextInput("Loot", "loot", style="paragraph",
                  placeholder="Treasure found (optional)",
                  required=False, max_length=2000),
        TextInput("Cliffhanger", "cliffhanger",
                  placeholder="Where did the session end? (optional)",
                  required=False, max_length=300),
    ]


def recap_dmnotes_fields() -> List[TextInput]:
    return [
        TextInput("DM Notes (never posted publicly)", "dm_notes",
                  style="paragraph",
                  placeholder="Plot threads, hooks for next session, secrets…",
                  required=True, max_length=4000),
    ]


def quest_add_fields() -> List[TextInput]:
    return [
        TextInput("Quest Title", "title",
                  placeholder="e.g. Find the missing miners", required=True, max_length=200),
        TextInput("Description", "description", style="paragraph",
                  placeholder="Quest details, objectives, rewards (optional)",
                  required=False, max_length=2000),
    ]


def quest_update_fields(*, current_status: str = "active") -> List[TextInput]:
    return [
        TextInput("Update text", "update_text", style="paragraph",
                  placeholder="What progressed on this quest?",
                  required=True, max_length=2000),
        TextInput("New status (optional)", "new_status",
                  placeholder="active, completed, failed, abandoned — leave blank to keep current",
                  required=False, max_length=20,
                  value=current_status),
    ]


def npc_add_fields() -> List[TextInput]:
    return [
        TextInput("NPC Name", "name",
                  placeholder="e.g. Sildar Hallwinter", required=True, max_length=200),
        TextInput("Role / occupation", "role",
                  placeholder="e.g. Lords' Alliance member (optional)",
                  required=False, max_length=200),
        TextInput("Location", "location",
                  placeholder="e.g. Phandalin (optional)", required=False, max_length=200),
        TextInput("Public notes", "public_notes", style="paragraph",
                  placeholder="What players know (visible to all unless DM-only)",
                  required=False, max_length=2000),
        TextInput("Secret notes", "secret_notes", style="paragraph",
                  placeholder="DM-only details (never shown to players)",
                  required=False, max_length=2000),
    ]


def alt_time_fields(*, campaign_tz: str = "UTC") -> List[TextInput]:
    return [
        TextInput("Proposed date (YYYY-MM-DD)", "date",
                  placeholder="2026-06-22", required=True, max_length=10),
        TextInput("Proposed start time (HH:MM, in campaign tz)",
                  "time_local", placeholder=f"e.g. 20:00 ({campaign_tz})",
                  required=True, max_length=5),
        TextInput("Why? (optional)", "reason", style="paragraph",
                  placeholder="e.g. I have a work conflict on the original date",
                  required=False, max_length=500),
    ]


def dmnote_add_fields() -> List[TextInput]:
    return [
        TextInput("Note title", "title",
                  placeholder="e.g. Plot hooks — Phandalin",
                  required=True, max_length=200),
        TextInput("Body", "body", style="paragraph",
                  placeholder="Your DM-only notes (ephemeral only)",
                  required=True, max_length=4000),
    ]
